"""Compute per-symbol open positions from trades + lots, scoped by account.

Pure function. Options are merged into their underlying ticker for
quantity/market value (equity-only) but contribute their cash flows to
cash_sunk_per_share. Period filtering applies to *realized P&L*, not to
the lots used for open positions (open positions are always "now").

Lots stored in the DB always carry the original buy quantity — the wash-sale
engine never decrements them when sells occur. This module FIFO-consumes the
oldest lot first against (a) sells in the trades table and (b) closed-quantity
totals from the Realized G/L import (used as a fallback when the user imported
G/L without the matching Transaction History, so the trade-table sells are
incomplete). The larger of the two sources wins per (account, ticker).
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from net_alpha.models.domain import Lot, Trade
from net_alpha.models.realized_gl import RealizedGLLot
from net_alpha.portfolio.models import (
    ClosedLotRow,
    OpenOptionRow,
    OpenShortOptionRow,
    PositionRow,
)
from net_alpha.pricing.provider import Quote

# Schwab appends a numeric suffix to an option's underlying after a split or
# special distribution ("GME" → "GME1"). The BTO may carry the original symbol
# while the matching STC and GL closure carry the adjusted symbol — economically
# the same position but two distinct tickers in the trade table. Strip the
# trailing digits when matching option events so the pair nets out.
_OPT_CORP_ACTION_SUFFIX = re.compile(r"\d+$")


def _opt_ticker_base(ticker: str) -> str:
    return _OPT_CORP_ACTION_SUFFIX.sub("", ticker)


def consume_lots_fifo(
    *,
    lots: Iterable[Lot],
    trades: Iterable[Trade],
    gl_closures: dict[tuple[str, str], float] | None = None,
    gl_option_closures: dict[tuple[str, str, float, object, str], float] | None = None,
) -> list[tuple[Lot, Decimal, Decimal]]:
    """FIFO-consume equity AND long-option lots by their closing events.

    Returns a list of (original_lot, remaining_qty, remaining_adjusted_basis).
    Lots fully consumed have remaining_qty == 0 (still returned so callers can
    inspect).

    Equity: closed_qty per (account, ticker) = max(sum_sells_in_trades, GL).
    Options: closed_qty per (account, ticker, strike, expiry, call_put) =
    max(sum_STC_trades, GL). STC = Sell with option_details whose basis_source
    is not "option_short_open" (those Sells open short positions, not close
    long ones, and have no lot to consume).

    GL is treated as canonical when it exceeds trade-side closes, since the
    Realized G/L CSV captures every closed lot regardless of whether the
    matching close trade was imported (in particular, Schwab does not log a
    transaction row for options that expire worthless — only a GL entry).
    """
    gl_closures = gl_closures or {}
    # Normalise the option-closure key: the repo helper returns expiry as an
    # ISO string, but Trade.option_details.expiry / Lot.option_details.expiry
    # are date objects. Coerce so all lookups in this function key the same
    # way. (Doing it here means callers don't have to remember.)
    raw_opt_closures = gl_option_closures or {}
    norm_opt_closures: dict[tuple[str, str, float, object, str], float] = {}
    for (acct, ticker, strike, expiry, cp), qty in raw_opt_closures.items():
        if isinstance(expiry, str):
            try:
                expiry = date.fromisoformat(expiry)
            except (TypeError, ValueError):
                continue
        nkey = (acct, _opt_ticker_base(ticker), strike, expiry, cp)
        norm_opt_closures[nkey] = norm_opt_closures.get(nkey, 0.0) + qty
    gl_option_closures = norm_opt_closures
    lots_list = list(lots)

    # --- Equity side ---
    sells_qty: dict[tuple[str, str], float] = defaultdict(float)
    for t in trades:
        if t.option_details is not None:
            continue
        if t.action.lower() == "sell":
            sells_qty[(t.account, t.ticker)] += float(t.quantity)
    eq_keys = set(sells_qty.keys()) | set(gl_closures.keys())
    closed_qty: dict[tuple[str, str], float] = {k: max(sells_qty.get(k, 0.0), gl_closures.get(k, 0.0)) for k in eq_keys}
    eq_grouped: dict[tuple[str, str], list[Lot]] = defaultdict(list)
    for lot in lots_list:
        if lot.option_details is not None:
            continue
        eq_grouped[(lot.account, lot.ticker)].append(lot)
    for group in eq_grouped.values():
        group.sort(key=lambda lt: lt.date)

    # --- Option side ---
    # Keys use the digit-stripped ticker base so corp-action variants (GME vs
    # GME1) match their pre-action counterparts.
    OptKey = tuple[str, str, float, object, str]
    opt_close_qty: dict[OptKey, float] = defaultdict(float)
    _STO_KINDS = {"option_short_open", "option_short_open_assigned"}
    for t in trades:
        if t.option_details is None or t.action.lower() != "sell":
            continue
        if t.basis_source in _STO_KINDS:
            continue  # STO opens a short, not a close of a long lot
        opt = t.option_details
        opt_close_qty[(t.account, _opt_ticker_base(t.ticker), opt.strike, opt.expiry, opt.call_put)] += float(
            t.quantity
        )
    opt_keys = set(opt_close_qty.keys()) | set(gl_option_closures.keys())
    opt_closed: dict[OptKey, float] = {
        k: max(opt_close_qty.get(k, 0.0), gl_option_closures.get(k, 0.0)) for k in opt_keys
    }
    opt_grouped: dict[OptKey, list[Lot]] = defaultdict(list)
    for lot in lots_list:
        if lot.option_details is None:
            continue
        opt = lot.option_details
        opt_grouped[(lot.account, _opt_ticker_base(lot.ticker), opt.strike, opt.expiry, opt.call_put)].append(lot)
    for group in opt_grouped.values():
        group.sort(key=lambda lt: lt.date)

    # --- Apply consumption ---
    remaining: dict[str, tuple[Decimal, Decimal]] = {
        lot.id: (Decimal(str(lot.quantity)), Decimal(str(lot.adjusted_basis))) for lot in lots_list
    }

    def _consume(group: list[Lot], to_take: Decimal) -> None:
        for lot in group:
            if to_take <= 0:
                break
            lot_qty, lot_basis = remaining[lot.id]
            if lot_qty <= 0:
                continue
            take = min(lot_qty, to_take)
            ratio = take / lot_qty
            remaining[lot.id] = (lot_qty - take, lot_basis - (lot_basis * ratio))
            to_take -= take

    for key, group in eq_grouped.items():
        _consume(group, Decimal(str(closed_qty.get(key, 0.0))))
    for key, group in opt_grouped.items():
        _consume(group, Decimal(str(opt_closed.get(key, 0.0))))

    return [(lot, *remaining[lot.id]) for lot in lots_list]


def open_lots_view(
    *,
    lots: Iterable[Lot],
    trades: Iterable[Trade],
    gl_closures: dict[tuple[str, str], float] | None = None,
    gl_option_closures: dict[tuple[str, str, float, object, str], float] | None = None,
) -> list[Lot]:
    """Return Lot view-objects representing only the still-open portion of
    each lot, after FIFO consumption by sells and GL closures.

    Use this for the lots table in the ticker drilldown, which used to query
    all rows from the DB and so showed long-closed BTOs (e.g. NVDA 220C
    12/19, TSLA option lots that expired or were sold-to-close) as if they
    were still open.

    Equity lots get their `quantity` reduced and their `cost_basis` /
    `adjusted_basis` prorated by the consumed ratio. Fully-closed lots are
    excluded.
    """
    consumed = consume_lots_fifo(
        lots=lots,
        trades=trades,
        gl_closures=gl_closures,
        gl_option_closures=gl_option_closures,
    )
    out: list[Lot] = []
    for lot, rem_qty, rem_basis in consumed:
        if rem_qty <= 0:
            continue
        if rem_qty == Decimal(str(lot.quantity)):
            out.append(lot)  # untouched
            continue
        ratio = rem_qty / Decimal(str(lot.quantity)) if lot.quantity else Decimal("1")
        out.append(
            Lot(
                id=lot.id,
                trade_id=lot.trade_id,
                account=lot.account,
                date=lot.date,
                ticker=lot.ticker,
                quantity=float(rem_qty),
                cost_basis=float(Decimal(str(lot.cost_basis)) * ratio),
                adjusted_basis=float(rem_basis),
                option_details=lot.option_details,
            )
        )
    return out


def compute_open_option_contracts(
    trades: Iterable[Trade],
    *,
    gl_option_closures: dict[tuple[str, float, object, str], float] | None = None,
) -> dict[str, Decimal]:
    """Per-underlying sum of |net qty| across all open option contracts.

    For each (ticker, strike, expiry, call_put) we compute signed net qty
    from trades (Buys add, Sells subtract). A BTO/STC pair zeros the long
    side; a STO/BTC pair zeros the short side.

    Closes that aren't represented in the trades table — expired worthless,
    assignment, or trade rows that simply weren't imported — show up in
    Schwab's Realized G/L CSV. ``gl_option_closures`` (keyed by
    (ticker, strike, expiry, call_put), value = total closed qty) shrinks
    |net qty| toward zero so those phantom-open contracts don't surface as
    "X opt open" badges on the holdings page.
    """
    net: dict[tuple[str, float, object, str], Decimal] = defaultdict(lambda: Decimal("0"))
    for t in trades:
        if t.option_details is None:
            continue
        opt = t.option_details
        key = (_opt_ticker_base(t.ticker), opt.strike, opt.expiry, opt.call_put)
        delta = Decimal(str(t.quantity))
        if t.action.lower() == "buy":
            net[key] += delta  # BTO long, BTC closes short (both add to net)
        else:
            net[key] -= delta  # STC closes long, STO opens short (both subtract)
    # Normalize closure keys onto the same digit-stripped base.
    raw_closures = gl_option_closures or {}
    closures: dict[tuple[str, float, object, str], float] = {}
    for (ticker, strike, expiry, cp), qty in raw_closures.items():
        nkey = (_opt_ticker_base(ticker), strike, expiry, cp)
        closures[nkey] = closures.get(nkey, 0.0) + qty
    for key, gl_qty in closures.items():
        if gl_qty <= 0:
            continue
        n = net.get(key, Decimal("0"))
        if n > 0:
            net[key] = max(n - Decimal(str(gl_qty)), Decimal("0"))
        elif n < 0:
            net[key] = min(n + Decimal(str(gl_qty)), Decimal("0"))
    out: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for (ticker, _s, _e, _cp), qty in net.items():
        if qty != 0:
            out[ticker] += abs(qty)
    return dict(out)


def compute_open_option_positions(
    trades: Iterable[Trade],
    lots: Iterable[Lot],
    *,
    ticker: str | None = None,
    account: str | None = None,
    gl_closures: dict[tuple[str, str], float] | None = None,
    gl_option_closures: dict[tuple[str, str, float, object, str], float] | None = None,
) -> list[OpenOptionRow]:
    """Return one row per open option position — long *or* short.

    Long rows come from the FIFO-consumed lot view (so partially-closed
    positions report only their remaining quantity and basis). Short rows
    come from the existing trade-aggregation logic (a chain of STO/BTC
    paired by (account, ticker_base, strike, expiry, cp)).

    Caller-provided ``ticker`` filters by digit-stripped underlying so
    corp-action variants (e.g. GME / GME1) collapse together.
    """
    trades_list = list(trades)
    lots_list = list(lots)
    if account:
        trades_list = [t for t in trades_list if t.account == account]
        lots_list = [lot for lot in lots_list if lot.account == account]

    rows: list[OpenOptionRow] = []

    # --- Long side: FIFO-consumed open lots filtered to options ---
    open_view = open_lots_view(
        lots=lots_list,
        trades=trades_list,
        gl_closures=gl_closures,
        gl_option_closures=gl_option_closures,
    )
    for lot in open_view:
        if lot.option_details is None:
            continue
        if ticker is not None and _opt_ticker_base(lot.ticker) != _opt_ticker_base(ticker):
            continue
        opt = lot.option_details
        rows.append(
            OpenOptionRow(
                side="long",
                account=lot.account,
                ticker=_opt_ticker_base(lot.ticker),
                strike=float(opt.strike),
                expiry=opt.expiry,
                call_put=opt.call_put,
                qty=Decimal(str(lot.quantity)),
                opened_at=lot.date,
                cash_basis=Decimal(str(lot.adjusted_basis)),
            )
        )

    # --- Short side: reuse existing aggregation ---
    short_rows = compute_open_short_option_positions(
        trades_list,
        ticker=ticker,
        gl_option_closures=gl_option_closures,
    )
    for s in short_rows:
        rows.append(
            OpenOptionRow(
                side="short",
                account=s.account,
                ticker=s.ticker,
                strike=s.strike,
                expiry=s.expiry,
                call_put=s.call_put,
                qty=s.qty_short,
                opened_at=s.opened_at,
                cash_basis=s.premium_received,
                contract_multiplier=s.contract_multiplier,
            )
        )

    rows.sort(key=lambda r: (r.expiry, r.ticker, r.strike, 0 if r.side == "long" else 1))
    return rows


def compute_open_short_option_positions(
    trades: Iterable[Trade],
    *,
    ticker: str | None = None,
    gl_option_closures: dict[tuple[str, str, float, object, str], float] | None = None,
) -> list[OpenShortOptionRow]:
    """Return one row per open short option position (STO not yet covered).

    A short option is "open" while the cumulative |sells - buys - GL closes|
    on a given (account, ticker, strike, expiry, call_put) is still negative.
    For each surviving group we report the remaining qty short, the net
    premium received on that chain (STO proceeds minus any BTC costs), and
    the date of the most recent STO that still has open contracts.

    The lots table only carries long lots; this fills in the short side
    so the ticker drilldown shows open CSPs/CCs.
    """
    trades = list(trades)
    # Per (account, ticker_base, strike, expiry, call_put):
    #   net_qty: positive for net long, negative for net short
    #   net_premium: cumulative STO proceeds - BTC costs (signed)
    #   latest_sto_date: most recent STO date in the chain
    Key = tuple[str, str, float, object, str]
    net_qty: dict[Key, Decimal] = defaultdict(lambda: Decimal("0"))
    net_premium: dict[Key, Decimal] = defaultdict(lambda: Decimal("0"))
    latest_sto_date: dict[Key, date] = {}
    for t in trades:
        if t.option_details is None:
            continue
        if ticker is not None and _opt_ticker_base(t.ticker) != _opt_ticker_base(ticker):
            continue
        opt = t.option_details
        key: Key = (t.account, _opt_ticker_base(t.ticker), opt.strike, opt.expiry, opt.call_put)
        delta = Decimal(str(t.quantity))
        if t.action.lower() == "buy":
            net_qty[key] += delta
            net_premium[key] -= Decimal(str(t.cost_basis or 0))
        else:
            net_qty[key] -= delta
            net_premium[key] += Decimal(str(t.proceeds or 0))
            prior = latest_sto_date.get(key)
            if prior is None or t.date > prior:
                latest_sto_date[key] = t.date

    # Apply GL closures: shrink net short toward zero (treat closures as
    # additional buys-to-close that simply weren't in the trade table).
    for (acct, ticker_raw, strike, expiry_iso, cp), gl_qty in (gl_option_closures or {}).items():
        if gl_qty <= 0:
            continue
        try:
            expiry = date.fromisoformat(expiry_iso) if isinstance(expiry_iso, str) else expiry_iso
        except (TypeError, ValueError):
            continue
        if ticker is not None and _opt_ticker_base(ticker_raw) != _opt_ticker_base(ticker):
            continue
        key = (acct, _opt_ticker_base(ticker_raw), strike, expiry, cp)
        n = net_qty.get(key, Decimal("0"))
        if n < 0:
            net_qty[key] = min(n + Decimal(str(gl_qty)), Decimal("0"))
        elif n > 0:
            net_qty[key] = max(n - Decimal(str(gl_qty)), Decimal("0"))

    rows: list[OpenShortOptionRow] = []
    for key, qty in net_qty.items():
        if qty >= 0:
            continue  # not short
        acct, sym, strike, expiry, cp = key
        rows.append(
            OpenShortOptionRow(
                account=acct,
                ticker=sym,
                strike=float(strike),
                expiry=expiry,  # type: ignore[arg-type]
                call_put=cp,
                qty_short=-qty,  # positive number of contracts short
                premium_received=net_premium[key].quantize(Decimal("0.01")),
                opened_at=latest_sto_date.get(key),
            )
        )
    rows.sort(key=lambda r: (r.expiry, r.ticker, r.strike))
    return rows


def compute_open_positions(
    *,
    trades: Iterable[Trade],
    lots: Iterable[Lot],
    prices: dict[str, Quote],
    period: tuple[int, int] | None = None,  # (year_start, year_end_exclusive); None = all time
    account: str | None = None,
    include_closed: bool = False,
    gl_closures: dict[tuple[str, str], float] | None = None,
    gl_option_closures: dict[tuple[str, str, float, object, str], float] | None = None,
    gl_lots: Iterable[RealizedGLLot] | None = None,
    as_of: date | None = None,
) -> list[PositionRow]:
    """Return positions sorted by market value desc (None last).

    When ``include_closed`` is True, also include symbols that have no open
    quantity but had Sell activity in the period — useful for "All" table mode
    where the user wants to see realized P/L on positions they've fully exited.

    Tickers with only open option exposure (e.g. an open sell-put on UUUU
    with zero shares) are also surfaced as rows with qty=0 so the user can
    drill into them.
    """
    trades = list(trades)
    lots = list(lots)
    gl_lots_list = list(gl_lots) if gl_lots is not None else None

    # Account scope
    if account:
        trades = [t for t in trades if t.account == account]
        lots = [lot for lot in lots if lot.account == account]
        gl_closures = {k: v for k, v in (gl_closures or {}).items() if k[0] == account} if gl_closures else None
        gl_option_closures = (
            {k: v for k, v in (gl_option_closures or {}).items() if k[0] == account} if gl_option_closures else None
        )
        if gl_lots_list is not None:
            gl_lots_list = [g for g in gl_lots_list if g.account_display == account]

    # Normalise GL option closures: the repo returns expiry as an ISO string,
    # but Trade.option_details.expiry is a date object — coerce so keys match.
    normalised_opt_closures: dict[tuple[str, str, float, object, str], float] = {}
    for (acct, ticker, strike, expiry_iso, cp), qty in (gl_option_closures or {}).items():
        try:
            expiry = date.fromisoformat(expiry_iso) if isinstance(expiry_iso, str) else expiry_iso
        except (TypeError, ValueError):
            continue
        normalised_opt_closures[(acct, ticker, strike, expiry, cp)] = (
            normalised_opt_closures.get((acct, ticker, strike, expiry, cp), 0.0) + qty
        )
    consumed = consume_lots_fifo(
        lots=lots,
        trades=trades,
        gl_closures=gl_closures,
        gl_option_closures=normalised_opt_closures,
    )
    # Same closures, sans the account key, for the per-underlying counter.
    option_closures_by_key: dict[tuple[str, float, object, str], float] = {}
    for (_acct, ticker, strike, expiry, cp), qty in normalised_opt_closures.items():
        key = (ticker, strike, expiry, cp)
        option_closures_by_key[key] = option_closures_by_key.get(key, 0.0) + qty
    open_options_by_sym = compute_open_option_contracts(trades, gl_option_closures=option_closures_by_key)

    # Aggregate equity-only quantities and basis from FIFO-reduced lots.
    # Two account maps:
    #   `open_accounts_by_sym` — accounts that currently hold equity OR
    #   options for the symbol. Drives the chip on open rows so a position
    #   that's only open in one account today doesn't show historical
    #   accounts that closed out before this period.
    #   `all_accounts_by_sym` — accounts with any trade activity ever for
    #   the symbol. Only used to populate the chip on closed-only rows.
    qty_by_sym: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    open_cost_by_sym: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    open_accounts_by_sym: dict[str, set[str]] = defaultdict(set)
    all_accounts_by_sym: dict[str, set[str]] = defaultdict(set)
    basis_known_by_sym: dict[str, bool] = defaultdict(bool)
    for lot, rem_qty, rem_basis in consumed:
        if lot.option_details is not None:
            continue
        if rem_qty <= 0:
            continue
        qty_by_sym[lot.ticker] += rem_qty
        open_cost_by_sym[lot.ticker] += rem_basis
        open_accounts_by_sym[lot.ticker].add(lot.account)
        # Provably-known basis: any open lot has a non-null, non-zero cost_basis.
        # Transferred-in lots default to None/0 until the user fills them in.
        if lot.cost_basis is not None and lot.cost_basis != 0:
            basis_known_by_sym[lot.ticker] = True
    # Long option lots with remaining qty contribute their account to the
    # symbol-level open-accounts map (they may live alongside equity rows
    # or stand alone on options-only rows).
    for lot, rem_qty, _ in consumed:
        if lot.option_details is None or rem_qty <= 0:
            continue
        open_accounts_by_sym[_opt_ticker_base(lot.ticker)].add(lot.account)

    # Phase 3 density extras: oldest-lot age and LT/ST split.
    LT_DAYS = 365
    today = as_of or date.today()
    oldest_open_by_sym: dict[str, date] = {}
    lt_qty_by_sym: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    st_qty_by_sym: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for lot, rem_qty, rem_basis in consumed:
        if lot.option_details is not None or rem_qty <= 0:
            continue
        sym = lot.ticker
        prior = oldest_open_by_sym.get(sym)
        if prior is None or lot.date < prior:
            oldest_open_by_sym[sym] = lot.date
        if (today - lot.date).days > LT_DAYS:
            lt_qty_by_sym[sym] += rem_qty
        else:
            st_qty_by_sym[sym] += rem_qty

    # Cash flows include ALL trades on the underlying ticker (equity AND options).
    # Transfer rows are counted using their user-set cost_basis / proceeds —
    # "Cash invested / sh" reflects what the user spent acquiring the shares,
    # regardless of which brokerage they paid at, so the column matches the
    # avg-basis side instead of dropping to $0 after a transfer-in.
    # Exception: assigned-put STO/synthetic-close pairs — the premium has
    # already been folded into the underlying stock's cost basis. Counting it
    # again here would inflate proceeds and double-credit realized P/L.
    _SKIP_AGG_SOURCES = {"option_short_open_assigned", "option_short_close_assigned"}
    buys_by_sym: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    sells_by_sym: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    premium_by_sym: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    trades_by_sym: dict[str, list[Trade]] = defaultdict(list)
    # Per-account, per-(ticker_base, strike, expiry, cp) net option qty.
    # Drives `open_accounts_by_sym` for short option positions, which don't
    # live in `consumed` (no Lot row for STO).
    OptAcctKey = tuple[str, str, float, object, str]
    opt_net_by_acct: dict[OptAcctKey, Decimal] = defaultdict(lambda: Decimal("0"))
    for t in trades:
        sym = t.ticker
        all_accounts_by_sym[sym].add(t.account)
        trades_by_sym[sym].append(t)
        # Per-account net option qty for short-position discovery.
        if t.option_details is not None:
            opt = t.option_details
            okey: OptAcctKey = (t.account, _opt_ticker_base(t.ticker), opt.strike, opt.expiry, opt.call_put)
            delta = Decimal(str(t.quantity))
            if t.action.lower() == "buy":
                opt_net_by_acct[okey] += delta
            else:
                opt_net_by_acct[okey] -= delta
        if t.basis_source in _SKIP_AGG_SOURCES:
            # Same skip applies to premium_received: assigned-put STO/synthetic-close
            # premium is already folded into the underlying basis. Counting it here
            # would double-credit it.
            continue
        # Option premium accumulation (for premium_received field).
        if t.option_details is not None:
            if t.proceeds is not None:
                premium_by_sym[sym] += Decimal(str(t.proceeds))
            if t.cost_basis is not None:
                premium_by_sym[sym] -= Decimal(str(t.cost_basis))
        if t.action.lower() == "buy":
            buys_by_sym[sym] += Decimal(str(t.cost_basis or 0))
        elif t.action.lower() == "sell":
            sells_by_sym[sym] += Decimal(str(t.proceeds or 0))

    # Apply per-account GL closures so net option qty reflects expirations,
    # assignments, and unimported BTC trades. Mirrors the aggregate logic in
    # `compute_open_option_contracts`.
    for (acct, ticker_base, strike, expiry, cp), gl_qty in normalised_opt_closures.items():
        if gl_qty <= 0:
            continue
        nkey: OptAcctKey = (acct, _opt_ticker_base(ticker_base), strike, expiry, cp)
        n = opt_net_by_acct.get(nkey, Decimal("0"))
        if n > 0:
            opt_net_by_acct[nkey] = max(n - Decimal(str(gl_qty)), Decimal("0"))
        elif n < 0:
            opt_net_by_acct[nkey] = min(n + Decimal(str(gl_qty)), Decimal("0"))
    for (acct, ticker_base, _strike, _expiry, _cp), qty in opt_net_by_acct.items():
        if qty != 0:
            open_accounts_by_sym[ticker_base].add(acct)

    # Realized P/L per symbol uses the canonical helper that pairs short-option
    # STO/BTC events instead of treating every Sell as a realization. See
    # net_alpha.portfolio.pnl.realized_pl_from_trades for the full rationale.
    from net_alpha.portfolio.pnl import realized_pl_from_trades

    # Bucket GL lots by ticker so per-symbol P&L only sees its own closures.
    gl_by_sym: dict[str, list[RealizedGLLot]] = defaultdict(list)
    if gl_lots_list is not None:
        for g in gl_lots_list:
            gl_by_sym[g.ticker].append(g)

    realized_by_sym: dict[str, Decimal] = {
        sym: realized_pl_from_trades(
            ts,
            period=period,
            gl_lots=gl_by_sym.get(sym) if gl_lots_list is not None else None,
        )
        for sym, ts in trades_by_sym.items()
    }

    def _account_chip(displays: tuple[str, ...]) -> str:
        if len(displays) <= 1:
            return displays[0] if displays else ""
        suffixes = sorted({a.split("/")[-1] for a in displays})
        return "+".join(suffixes)

    rows: list[PositionRow] = []
    for sym, qty in qty_by_sym.items():
        if qty == 0:
            continue
        open_cost = open_cost_by_sym[sym]
        avg_basis = (open_cost / qty) if qty else Decimal("0")
        cash_sunk = (buys_by_sym[sym] - sells_by_sym[sym]) / qty if qty else Decimal("0")
        quote = prices.get(sym)
        market_value = (qty * quote.price) if quote else None
        unrealized = (market_value - open_cost) if market_value is not None else None
        oldest = oldest_open_by_sym.get(sym)
        days_held = (today - oldest).days if oldest is not None else None
        accounts_tuple = tuple(sorted(open_accounts_by_sym[sym]))
        rows.append(
            PositionRow(
                symbol=sym,
                accounts=accounts_tuple,
                qty=qty,
                market_value=market_value,
                open_cost=open_cost,
                avg_basis=avg_basis,
                cash_sunk_per_share=cash_sunk,
                realized_pl=realized_by_sym[sym],
                unrealized_pl=unrealized,
                open_option_contracts=open_options_by_sym.get(sym, Decimal("0")),
                days_held=days_held,
                lt_qty=lt_qty_by_sym[sym],
                st_qty=st_qty_by_sym[sym],
                premium_received=premium_by_sym[sym].quantize(Decimal("0.01")),
                basis_known=basis_known_by_sym.get(sym, False),
                account_chip=_account_chip(accounts_tuple),
                account_displays=accounts_tuple,
            )
        )
    # Tickers with only open option exposure (no equity lot): emit a qty=0 row
    # so the user can still drill in. Skipped when account-scoped emits no
    # open-accounts entry, since the option trade itself populates that map.
    seen_open = {r.symbol for r in rows}
    for sym, opt_contracts in open_options_by_sym.items():
        if sym in seen_open or opt_contracts == 0:
            continue
        if qty_by_sym.get(sym, Decimal("0")) != 0:
            continue
        accounts_tuple = tuple(sorted(open_accounts_by_sym[sym]))
        rows.append(
            PositionRow(
                symbol=sym,
                accounts=accounts_tuple,
                qty=Decimal("0"),
                market_value=None,
                open_cost=Decimal("0"),
                avg_basis=Decimal("0"),
                cash_sunk_per_share=Decimal("0"),
                realized_pl=realized_by_sym.get(sym, Decimal("0")),
                unrealized_pl=None,
                open_option_contracts=opt_contracts,
                account_chip=_account_chip(accounts_tuple),
                account_displays=accounts_tuple,
            )
        )
    if include_closed:
        seen = {r.symbol for r in rows}
        # Closed symbols: had Sell activity (period-scoped if a period is set)
        # but no remaining open quantity. Use the all-trade-accounts map here
        # so a fully-closed symbol still surfaces every account it ever traded
        # in — that's the historical chip semantic for the closed view.
        for sym, realized in realized_by_sym.items():
            if sym in seen:
                continue
            if qty_by_sym.get(sym, Decimal("0")) != 0:
                continue
            accounts_tuple = tuple(sorted(all_accounts_by_sym[sym]))
            rows.append(
                PositionRow(
                    symbol=sym,
                    accounts=accounts_tuple,
                    qty=Decimal("0"),
                    market_value=Decimal("0"),
                    open_cost=Decimal("0"),
                    avg_basis=Decimal("0"),
                    cash_sunk_per_share=Decimal("0"),
                    realized_pl=realized,
                    unrealized_pl=Decimal("0"),
                    account_chip=_account_chip(accounts_tuple),
                    account_displays=accounts_tuple,
                )
            )
    rows.sort(key=lambda r: (r.market_value is None, -(r.market_value or Decimal("0"))))
    return rows


def compute_closed_lots(
    gl_lots: Iterable[RealizedGLLot],
    *,
    period: tuple[int, int] | None = None,
    account_display: str | None = None,
) -> list[ClosedLotRow]:
    """Aggregate Realized G/L lots into ClosedLotRow records for the Closed tab.

    ``period`` is ``(year_start_inclusive, year_end_exclusive)`` matched against
    each lot's ``closed_date.year`` — None means lifetime. ``account_display``
    filters to a single account when provided.

    Sorted by close date descending so the most recent closures land at the
    top. Realized P/L is ``proceeds - cost_basis`` (Schwab GL data already has
    wash-sale adjustments folded into the cost basis when applicable).
    """
    out: list[ClosedLotRow] = []
    for lot in gl_lots:
        if account_display is not None and lot.account_display != account_display:
            continue
        if period is not None and not (period[0] <= lot.closed_date.year < period[1]):
            continue
        cost_basis = Decimal(str(lot.cost_basis))
        proceeds = Decimal(str(lot.proceeds))
        out.append(
            ClosedLotRow(
                account=lot.account_display,
                ticker=lot.ticker,
                qty=Decimal(str(lot.quantity)),
                cost_basis=cost_basis,
                proceeds=proceeds,
                realized_pl=proceeds - cost_basis,
                opened_date=lot.opened_date,
                closed_date=lot.closed_date,
                term=lot.term,
                wash_sale=lot.wash_sale,
                disallowed_loss=Decimal(str(lot.disallowed_loss)),
                option_strike=lot.option_strike,
                option_expiry=lot.option_expiry,
                option_call_put=lot.option_call_put,
            )
        )
    out.sort(key=lambda r: r.closed_date, reverse=True)
    return out
