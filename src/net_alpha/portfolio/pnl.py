"""KPI aggregations for the Portfolio page header.

period: (year_start_inclusive, year_end_exclusive), e.g. (2026, 2027) for YTD 2026,
or None for "Lifetime" (no period filter).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date as _date
from decimal import Decimal

from net_alpha.models.domain import Lot, Trade, WashSaleViolation
from net_alpha.models.realized_gl import RealizedGLLot
from net_alpha.portfolio.models import KpiSet, WashImpact
from net_alpha.portfolio.positions import compute_today_change, consume_lots_fifo
from net_alpha.pricing.provider import Quote

# BTC basis_source values whose realization pairs with a matching STO. Excludes
# ``option_short_close_assigned`` because that flow folds the STO premium into
# the assigned long-stock basis — counting it again here would double-credit
# the user.
_BTC_REALIZE_SOURCES = frozenset({"option_short_close", "option_short_close_expiry"})

# STO sources whose premium is the proceeds side of a short. The "_assigned"
# variant is paired through the put_assignment / synthetic-close flow and
# folded into long-stock basis, so it's intentionally NOT considered for
# trade-pair realization.
_STO_PAIRABLE_SOURCES = frozenset({"option_short_open"})

# Settlement offset between Schwab's GL `closed_date` and the matching trade
# row's `date`. T+1 settlement means a BTC traded on the 18th can show up as
# closed_date=19th in GL — but a Friday trade settles Monday (3 calendar
# days) and a Friday trade before a Monday market holiday settles Tuesday
# (4 days). 4 days covers both without paying for a holiday calendar.
_GL_PAIR_DAY_TOLERANCE = 4


def realized_pl_from_trades(
    trades: Iterable[Trade],
    period: tuple[int, int] | None,
    *,
    gl_lots: Iterable[RealizedGLLot] | None = None,
    include_disallowed_loss: bool = True,
) -> Decimal:
    """Sum realized P&L across a list of trades.

    Four flows are handled:

    1. **Long-lot Sells** (equity sales, STC of long options): realized on the
       Sell date as ``proceeds - cost_basis``.

    2. **Short-option STO**: an open event — premium is *not* realized until
       the position closes. STOs contribute zero on their own row.

    3. **Short-option BTC** (``option_short_close`` / ``..._expiry``): paired
       with the matching STO(s) on (account, ticker, strike, expiry, call_put).
       Premium is **distributed by contract quantity** across the BTCs that
       close it: ``premium_share = total_STO_premium × btc_qty / total_STO_qty``.
       Realized at the BTC = ``premium_share − btc.cost_basis``. Without the
       quantity scaling, two 1-contract BTCs closing a 2-contract STO would
       each credit the full premium and double-count it.

    4. **GL as canonical when present** (when ``gl_lots`` is provided): the
       Schwab Realized G/L CSV is the broker's authoritative per-lot record —
       it captures expirations the Transactions CSV silently drops AND the
       wash-sale-unadjusted basis used for tax reporting. When a trade close
       has any GL row for the same ``(account, ticker, option_key)`` within
       ``_GL_PAIR_DAY_TOLERANCE`` of the trade date, the GL row is taken as
       the source of truth and the trade-side P&L for that close is dropped —
       Schwab consolidates multi-lot trades into a single Transaction row but
       splits them per-opened-lot in GL, so 1-trade-claims-1-GL-lot pairing
       drifts whenever the row counts disagree. Trade closes with no matching
       GL coverage (e.g., closures from before the user's GL CSV starts) keep
       contributing trade-side P&L.
    """
    trades = list(trades)
    total = Decimal("0")

    sto_premium: dict[tuple, Decimal] = defaultdict(lambda: Decimal("0"))
    sto_qty: dict[tuple, Decimal] = defaultdict(lambda: Decimal("0"))
    for t in trades:
        if not t.is_sell():
            continue
        if t.basis_source not in _STO_PAIRABLE_SOURCES:
            continue
        if t.option_details is None:
            continue
        opt = t.option_details
        key = (t.account, t.ticker, opt.strike, opt.expiry, opt.call_put)
        sto_premium[key] += Decimal(str(t.proceeds or 0))
        sto_qty[key] += Decimal(str(t.quantity))

    gl_close_dates_by_key = _index_gl_close_dates(gl_lots) if gl_lots is not None else None

    def _gl_covers(t: Trade) -> bool:
        if gl_close_dates_by_key is None:
            return False
        if t.option_details is not None:
            opt = t.option_details
            key: tuple = (t.account, t.ticker, opt.strike, opt.expiry, opt.call_put)
        else:
            key = (t.account, t.ticker, None, None, None)
        for cd in gl_close_dates_by_key.get(key, ()):
            if abs((t.date - cd).days) <= _GL_PAIR_DAY_TOLERANCE:
                return True
        return False

    for t in trades:
        if t.is_sell():
            # STOs and the assigned-STO variant are *not* realized at open —
            # their realization is folded into the matching close (BTC, expiry
            # synth, or rolled into stock basis on assignment).
            if t.basis_source.startswith("option_short_open"):
                continue
            if period is not None and not (period[0] <= t.date.year < period[1]):
                continue
            if _gl_covers(t):
                continue
            total += Decimal(str((t.proceeds or 0) - (t.cost_basis or 0)))
        elif t.is_buy():
            if t.basis_source not in _BTC_REALIZE_SOURCES:
                continue
            if t.option_details is None:
                continue
            if period is not None and not (period[0] <= t.date.year < period[1]):
                continue
            if _gl_covers(t):
                continue
            opt = t.option_details
            key = (t.account, t.ticker, opt.strike, opt.expiry, opt.call_put)
            total_sto_qty = sto_qty.get(key, Decimal("0"))
            btc_qty = Decimal(str(t.quantity))
            if total_sto_qty > 0:
                premium_share = sto_premium.get(key, Decimal("0")) * btc_qty / total_sto_qty
            else:
                premium_share = Decimal("0")
            total += premium_share - Decimal(str(t.cost_basis or 0))

    if gl_lots is not None:
        for gl in gl_lots:
            if period is not None and not (period[0] <= gl.closed_date.year < period[1]):
                continue
            # Tax-recognized realized P&L: a wash-sale-disallowed loss is added
            # to the replacement lot's basis instead of reducing this lot's P&L,
            # so the period total is ``proceeds - cost_basis + disallowed_loss``.
            # Schwab's UI and Form 8949 show this recognized figure. Pass
            # ``include_disallowed_loss=False`` to get the *economic* P&L
            # instead — the actual cash netted, ignoring the basis shift.
            lot_pl = Decimal(str(gl.proceeds)) - Decimal(str(gl.cost_basis))
            if include_disallowed_loss:
                lot_pl += Decimal(str(gl.disallowed_loss))
            total += lot_pl

    return total


def _index_gl_close_dates(
    gl_lots: Iterable[RealizedGLLot],
) -> dict[tuple, list[_date]]:
    """Group GL close dates by ``(account, ticker, option_key)``.

    Used to decide whether a trade close has any GL coverage for that key
    within the settlement-day tolerance window. Coverage is a *set* check
    (does any GL lot exist for this key near this date?) rather than a 1:1
    pairing — Schwab consolidates multiple opened lots into a single trade
    row but emits one GL row per opened lot, so a 1-trade-claims-1-GL-lot
    walk over-counts whenever those row counts disagree.
    """
    out: dict[tuple, list[_date]] = defaultdict(list)
    for gl in gl_lots:
        if gl.option_strike is not None:
            try:
                expiry_d: _date | None = _date.fromisoformat(gl.option_expiry) if gl.option_expiry else None
            except ValueError:
                expiry_d = None
            if expiry_d is None:
                continue
            key: tuple = (
                gl.account_display,
                gl.ticker,
                float(gl.option_strike),
                expiry_d,
                gl.option_call_put,
            )
        else:
            key = (gl.account_display, gl.ticker, None, None, None)
        out[key].append(gl.closed_date)
    return out


# Backwards-compat alias: older callers in this module reference _realized_in.
_realized_in = realized_pl_from_trades


def _gl_closures_from_lots(
    gl_list: Iterable[RealizedGLLot],
) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str, float, str, str], float]]:
    """Aggregate Realized G/L rows into the closure dicts that
    ``consume_lots_fifo`` expects (equity, options).

    Mirrors ``Repository.get_equity_gl_closures`` / ``get_option_gl_closures``
    but works in-memory off a list, so KPI math doesn't need a Repository.
    """
    eq: dict[tuple[str, str], float] = {}
    opt: dict[tuple[str, str, float, str, str], float] = {}
    for r in gl_list:
        if r.option_strike is None:
            key_eq = (r.account_display, r.ticker)
            eq[key_eq] = eq.get(key_eq, 0.0) + float(r.quantity)
        else:
            key_opt = (r.account_display, r.ticker, r.option_strike, r.option_expiry, r.option_call_put)
            opt[key_opt] = opt.get(key_opt, 0.0) + float(r.quantity)
    return eq, opt


def _open_market_and_basis(
    consumed: Iterable[tuple[Lot, Decimal, Decimal]],
    prices: dict[str, Quote],
) -> tuple[Decimal, Decimal, tuple[str, ...]]:
    """Return (priced_market, priced_basis, missing_symbols).

    Input is the output of ``consume_lots_fifo`` — ``(lot, rem_qty, rem_basis)``
    triples. Fully-closed lots (rem_qty == 0) and option lots are skipped.

    priced_market = Σ(rem_qty × price) over open equity lots that have a quote.
    priced_basis  = Σ(rem_basis) over the SAME priced lots.
    missing_symbols = sorted unique tickers we couldn't price.

    Computing both market AND basis from the same priced subset means
    ``priced_market - priced_basis`` is a correct unrealized P/L for that
    subset, even when prices for some lots are missing. Callers can then
    surface partial sums alongside a "N symbols unpriced" caveat instead
    of throwing the whole aggregate away.
    """
    total_value: Decimal = Decimal("0")
    priced_basis: Decimal = Decimal("0")
    missing: set[str] = set()
    for lot, rem_qty, rem_basis in consumed:
        if rem_qty <= 0:
            continue
        if lot.option_details is not None:
            continue  # equity-only for KPI market value
        quote = prices.get(lot.ticker)
        if quote is None:
            missing.add(lot.ticker)
            continue
        total_value += rem_qty * quote.price
        priced_basis += rem_basis  # already total dollars, prorated by FIFO consumption
    return total_value, priced_basis, tuple(sorted(missing))


def compute_kpis(
    *,
    trades: Iterable[Trade],
    lots: Iterable[Lot],
    prices: dict[str, Quote],
    period_label: str,
    period: tuple[int, int] | None,
    account: str | None,
    gl_lots: Iterable[RealizedGLLot] | None = None,
) -> KpiSet:
    trades = list(trades)
    lots = list(lots)
    gl_list = list(gl_lots) if gl_lots is not None else None
    if account:
        trades = [t for t in trades if t.account == account]
        lots = [lot for lot in lots if lot.account == account]
        if gl_list is not None:
            gl_list = [g for g in gl_list if g.account_display == account]

    period_realized = _realized_in(trades, period, gl_lots=gl_list)
    lifetime_realized = _realized_in(trades, None, gl_lots=gl_list)
    period_realized_economic = _realized_in(trades, period, gl_lots=gl_list, include_disallowed_loss=False)
    lifetime_realized_economic = _realized_in(trades, None, gl_lots=gl_list, include_disallowed_loss=False)

    # FIFO-consume buy lots against trade-side sells AND any imported Realized
    # G/L closures — `lot.quantity` is the original buy size and is never
    # decremented in storage, so iterating raw lots double-counts every share
    # the user has already sold. See ``portfolio.positions.consume_lots_fifo``.
    eq_closures, opt_closures = _gl_closures_from_lots(gl_list or [])
    consumed = consume_lots_fifo(
        lots=lots,
        trades=trades,
        gl_closures=eq_closures,
        gl_option_closures=opt_closures,
    )

    market, basis, missing = _open_market_and_basis(consumed, prices)
    has_equity_lots = any(lot.option_details is None for lot in lots)
    # "All unpriced" = we have equity lots but couldn't price a single one.
    # Keep showing — in that case so users see "no data" rather than a misleading $0.
    all_unpriced = has_equity_lots and bool(missing) and market == 0 and basis == 0
    if all_unpriced:
        period_unrealized = None
        lifetime_unrealized = None
        open_value = None
        lifetime_net_pl = None
    else:
        unrealized = market - basis  # correctly scoped to priced subset
        period_unrealized = unrealized  # unrealized is "now"; period only relabels the card
        lifetime_unrealized = unrealized
        open_value = market
        lifetime_net_pl = lifetime_realized + unrealized

    # Today tile: per-lot (price - prev_close) * remaining_qty, skipping lots
    # with no prev close. Uses the FIFO-consumed quantities so a closed lot
    # doesn't keep contributing to today's $ change.
    quotes_with_prev = {sym: (q.price, q.previous_close) for sym, q in prices.items()}
    open_lots_by_sym: list[tuple[str, Decimal]] = [
        (lot.ticker, rem_qty) for lot, rem_qty, _ in consumed if rem_qty > 0 and lot.option_details is None
    ]
    today_change, prev_value = compute_today_change(open_lots_by_sym, quotes_with_prev)
    today_pct: Decimal | None = (today_change / prev_value) if prev_value else None

    return KpiSet(
        period_label=period_label,
        period_realized=period_realized,
        period_unrealized=period_unrealized,
        lifetime_realized=lifetime_realized,
        lifetime_unrealized=lifetime_unrealized,
        open_position_value=open_value,
        lifetime_net_pl=lifetime_net_pl,
        missing_symbols=missing,
        today_change=today_change,
        today_pct=today_pct,
        period_realized_economic=period_realized_economic,
        lifetime_realized_economic=lifetime_realized_economic,
    )


def compute_wash_impact(
    *,
    violations: Iterable[WashSaleViolation],
    period_label: str,
    period: tuple[int, int] | None,
    account: str | None,
) -> WashImpact:
    rows = list(violations)
    if account:
        rows = [v for v in rows if v.loss_account == account or v.buy_account == account]
    if period is not None:
        rows = [v for v in rows if v.loss_sale_date and period[0] <= v.loss_sale_date.year < period[1]]
    disallowed = sum((Decimal(str(v.disallowed_loss)) for v in rows), start=Decimal("0"))
    return WashImpact(
        period_label=period_label,
        disallowed_total=disallowed,
        violation_count=len(rows),
        confirmed_count=sum(1 for v in rows if v.confidence == "Confirmed"),
        probable_count=sum(1 for v in rows if v.confidence == "Probable"),
        unclear_count=sum(1 for v in rows if v.confidence == "Unclear"),
    )
