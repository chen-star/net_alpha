"""Pure-function builders for the math-explainer panels on Total Return
and Unrealized P/L KPI tiles. No I/O. The web layer wires repo + pricing
data in; this module returns dataclasses ready for Jinja.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class TotalReturnBreakdown:
    """Payload for the Total Return explainer panel.

    `delta_unrealized_residual` is computed as a residual
    (`total_return - realized_in_period`) rather than from a historical
    unrealized snapshot. This avoids needing to mark every position to
    market at the period boundary.

    The `unpriced_*` fields surface lots that were silently dropped from the
    starting-value anchor because their close was missing from the cache —
    when non-zero, the rendered Total Return is an *overcount* (starting too
    low → ending-minus-starting too high), and the user should re-warm the
    historical cache.
    """

    period_label: str
    ending_value: Decimal
    starting_value: Decimal
    contributions: Decimal
    total_return: Decimal
    realized_in_period: Decimal
    delta_unrealized_residual: Decimal
    is_lifetime: bool
    unpriced_lot_count: int = 0
    unpriced_basis_total: Decimal = Decimal("0")
    unpriced_tickers: tuple[str, ...] = ()


@dataclass(frozen=True)
class UnrealizedLongLine:
    """One row in the long stock/option section of the unrealized panel."""

    symbol: str  # e.g. "AAPL" or "AAPL 180C 2026-06-20"
    qty: Decimal
    last_price: Decimal  # for long options without a quote, 0 (carried at basis)
    cost_basis: Decimal
    unrealized: Decimal


@dataclass(frozen=True)
class UnrealizedShortOptionLine:
    """One row in the short options section. Includes intermediate values
    so the renderer can show the user how the estimate was built."""

    symbol_display: str  # e.g. "SPY 500P 2026-06-20"
    contracts: int  # |qty short|
    premium_received: Decimal  # positive
    spot: Decimal
    intrinsic_per_share: Decimal
    days_total: int
    days_remaining: int
    time_value_per_share: Decimal
    est_value_to_close: Decimal  # total liability across all contracts
    unrealized: Decimal  # premium_received - est_value_to_close
    is_covered: bool  # True for calls (covered call notation)


@dataclass(frozen=True)
class UnrealizedBreakdown:
    """Payload for the Unrealized P/L explainer panel.

    Per-line lists (`long_lines`, `short_option_lines`) are kept for callers
    that want a per-position drilldown; the panel template uses only the
    aggregated totals for a simpler "formula and numbers" view.
    """

    long_lines: list[UnrealizedLongLine]
    long_market_total: Decimal  # Σ market value across long lines
    long_cost_total: Decimal  # Σ cost basis across long lines
    long_subtotal: Decimal  # = long_market_total − long_cost_total
    short_option_lines: list[UnrealizedShortOptionLine]
    short_premium_total: Decimal  # Σ premium received across short options
    short_liability_total: Decimal  # Σ est. value to close across short options
    short_subtotal: Decimal  # = short_premium_total − short_liability_total
    total_unrealized: Decimal
    excluded_count: int  # lots/shorts skipped because no quote available


@dataclass(frozen=True)
class AccountValueBreakdown:
    """Payload for the Total Account Value explainer panel.

    Both equations sum to the same `total_account_value`:

      Composition: cash_balance
                 + long_stock_mv
                 + long_option_mv
                 − short_option_liability   (positive number, subtracted)

      Source:      net_contributed
                 + lifetime_realized_economic   (after wash, the cash one)
                 + non_contribution_cash_flow   (dividends + interest − fees)
                 + share_transfer_basis_net     (in-kind transfers' cost basis)
                 + current_unrealized
                 + reconciliation_residual      (anything we couldn't classify)

    `lifetime_realized_economic` MUST be the wash-adjusted economic figure
    (`KpiSet.lifetime_realized_economic`), not the tax-recognized one — the
    cash account never sees a wash-sale disallowance.

    `non_contribution_cash_flow` captures cash events that move the balance
    but are neither user contributions nor trade P&L: dividends, interest,
    fees. Without this term the composition over-counts those amounts.

    `share_transfer_basis_net` is the cost basis of in-kind share transfers
    (`Trade.basis_source` of "transfer_in" / "transfer_out"). These move
    shares (not cash) into/out of the account, so the lots' cost basis adds
    value to the composition without any matching cash flow or P&L event;
    the source equation needs an explicit term to balance them.

    `reconciliation_residual` is the catch-all the builder fills in so the
    two equations agree by construction. A non-zero residual means the
    explainer is missing a flow we don't yet model (a corporate action
    write-up, an option assignment basis adjustment we haven't propagated,
    etc.) — the panel surfaces it as a labelled row so users can see the
    gap rather than the page 500ing.
    """

    # Composition (Equation 1)
    cash_balance: Decimal
    long_stock_mv: Decimal
    long_option_mv: Decimal
    short_option_liability: Decimal  # positive number, subtracted in the equation
    # Source (Equation 2)
    net_contributed: Decimal
    lifetime_realized_economic: Decimal
    non_contribution_cash_flow: Decimal  # dividends + interest − fees
    share_transfer_basis_net: Decimal  # in-kind transfer-in basis − transfer-out basis
    current_unrealized: Decimal
    reconciliation_residual: Decimal  # composition − (other source terms); zero on clean books
    # Reconciliation total — both equations agree to this value
    total_account_value: Decimal
    # Caveat data
    missing_symbols: tuple[str, ...]
    has_short_options: bool
    fetched_at: dt.datetime | None


def _estimate_short_option_liability(
    *,
    row,  # OpenShortOptionRow
    spot: Decimal,
    as_of: dt.date,
) -> tuple[Decimal, Decimal, int, int, Decimal, Decimal]:
    """Estimate the cost-to-close for one open short option row.

    Returns: (est_liability, intrinsic_per_share, days_total, days_remaining,
              time_value_per_share, premium_per_share).

    Math mirrors `pnl._short_option_unrealized_adjustment()`.
    Pure — no I/O, no quote lookup (caller resolves spot first).
    """
    strike = Decimal(str(row.strike))
    if row.call_put == "P":
        intrinsic = max(Decimal("0"), strike - spot)
    else:
        intrinsic = max(Decimal("0"), spot - strike)
    days_total = max(1, (row.expiry - row.opened_at).days)
    days_remaining = max(0, (row.expiry - as_of).days)
    contracts = row.qty_short
    multiplier = Decimal(str(row.contract_multiplier))
    premium_per_share = row.premium_received / contracts / multiplier if contracts > 0 else Decimal("0")
    time_value = premium_per_share * (Decimal(days_remaining) / Decimal(days_total))
    est_per_share = max(intrinsic, time_value)
    est_liability = (est_per_share * contracts * multiplier).quantize(Decimal("0.01"))
    return (
        est_liability,
        intrinsic,
        days_total,
        days_remaining,
        time_value,
        premium_per_share,
    )


def build_total_return_breakdown(
    *,
    period_label: str,
    ending_value: Decimal,
    starting_value: Decimal,
    contributions: Decimal,
    realized_in_period: Decimal,
    is_lifetime: bool,
    unpriced_lot_count: int = 0,
    unpriced_basis_total: Decimal = Decimal("0"),
    unpriced_tickers: tuple[str, ...] = (),
) -> TotalReturnBreakdown:
    """Build the Total Return explainer payload.

    All inputs are computed by the caller (route handler). This module
    just packages the math into a renderable dataclass and computes the
    `delta_unrealized_residual` (Total Return − Realized).
    """
    total_return = ending_value - starting_value - contributions
    delta_unrealized_residual = total_return - realized_in_period
    return TotalReturnBreakdown(
        period_label=period_label,
        ending_value=ending_value,
        starting_value=starting_value,
        contributions=contributions,
        total_return=total_return,
        realized_in_period=realized_in_period,
        delta_unrealized_residual=delta_unrealized_residual,
        is_lifetime=is_lifetime,
        unpriced_lot_count=unpriced_lot_count,
        unpriced_basis_total=unpriced_basis_total,
        unpriced_tickers=unpriced_tickers,
    )


def build_unrealized_breakdown(
    *,
    consumed: list,  # list[(Lot, Decimal rem_qty, Decimal rem_basis)]
    short_option_rows: list,  # list[OpenShortOptionRow]
    prices: dict,  # {ticker: Quote}
    as_of: dt.date,
) -> UnrealizedBreakdown:
    """Walk the FIFO-consumed lots and the open short option positions to
    build a row-by-row unrealized breakdown.

    Long-side math mirrors `pnl._open_market_and_basis()`.
    Short-option math mirrors `pnl._short_option_unrealized_adjustment()`.
    Keep the math here in sync with those functions when either changes.
    """
    long_lines: list[UnrealizedLongLine] = []
    short_lines: list[UnrealizedShortOptionLine] = []
    long_subtotal = Decimal("0")
    long_market_total = Decimal("0")
    long_cost_total = Decimal("0")
    short_subtotal = Decimal("0")
    short_premium_total = Decimal("0")
    short_liability_total = Decimal("0")
    excluded = 0

    for lot, rem_qty, rem_basis in consumed:
        if rem_qty <= 0:
            continue
        if lot.option_details is not None:
            # Long option lot. Past-expiry → skip silently. Otherwise carried
            # at basis (market = basis → unrealized = 0); contributes
            # rem_basis to BOTH market and cost so the aggregate reads
            # consistently.
            if lot.option_details.expiry < as_of:
                continue
            opt = lot.option_details
            long_market_total += rem_basis
            long_cost_total += rem_basis
            long_lines.append(
                UnrealizedLongLine(
                    symbol=f"{lot.ticker} {opt.strike}{opt.call_put} {opt.expiry.isoformat()}",
                    qty=rem_qty,
                    last_price=Decimal("0"),
                    cost_basis=rem_basis,
                    unrealized=Decimal("0"),
                )
            )
            continue
        quote = prices.get(lot.ticker)
        if quote is None or quote.price is None:
            excluded += 1
            continue
        last = Decimal(str(quote.price))
        market = (rem_qty * last).quantize(Decimal("0.01"))
        unrealized = (market - rem_basis).quantize(Decimal("0.01"))
        long_subtotal += unrealized
        long_market_total += market
        long_cost_total += rem_basis
        long_lines.append(
            UnrealizedLongLine(
                symbol=lot.ticker,
                qty=rem_qty,
                last_price=last,
                cost_basis=rem_basis,
                unrealized=unrealized,
            )
        )

    for row in short_option_rows:
        if row.opened_at is None:
            continue
        quote = prices.get(row.ticker)
        if quote is None or quote.price is None:
            excluded += 1
            continue
        spot = Decimal(str(quote.price))
        strike = Decimal(str(row.strike))
        (
            est_liability,
            intrinsic,
            days_total,
            days_remaining,
            time_value,
            _premium_per_share,
        ) = _estimate_short_option_liability(row=row, spot=spot, as_of=as_of)
        unrealized = (row.premium_received - est_liability).quantize(Decimal("0.01"))
        short_subtotal += unrealized
        short_premium_total += row.premium_received
        short_liability_total += est_liability
        short_lines.append(
            UnrealizedShortOptionLine(
                symbol_display=f"{row.ticker} {strike}{row.call_put} {row.expiry.isoformat()}",
                contracts=int(row.qty_short),
                premium_received=row.premium_received,
                spot=spot,
                intrinsic_per_share=intrinsic,
                days_total=days_total,
                days_remaining=days_remaining,
                time_value_per_share=time_value,
                est_value_to_close=est_liability,
                unrealized=unrealized,
                is_covered=(row.call_put == "C"),
            )
        )

    return UnrealizedBreakdown(
        long_lines=long_lines,
        long_market_total=long_market_total.quantize(Decimal("0.01")),
        long_cost_total=long_cost_total.quantize(Decimal("0.01")),
        long_subtotal=long_subtotal,
        short_option_lines=short_lines,
        short_premium_total=short_premium_total.quantize(Decimal("0.01")),
        short_liability_total=short_liability_total.quantize(Decimal("0.01")),
        short_subtotal=short_subtotal,
        total_unrealized=long_subtotal + short_subtotal,
        excluded_count=excluded,
    )


def build_account_value_breakdown(
    *,
    consumed: list,  # list[(Lot, Decimal rem_qty, Decimal rem_basis)]
    short_option_rows: list,  # list[OpenShortOptionRow]
    prices: dict,  # {ticker: Quote}
    cash_balance: Decimal,
    net_contributed: Decimal,
    lifetime_realized_economic: Decimal,
    non_contribution_cash_flow: Decimal,
    share_transfer_basis_net: Decimal,
    missing_symbols: tuple[str, ...],
    fetched_at: dt.datetime | None,
    as_of: dt.date,
) -> AccountValueBreakdown:
    """Build the Total Account Value explainer payload.

    Splits the open position MV into long stock vs long option (carried at
    basis when no quote) and short option liability (intrinsic + straight-
    line time decay). Long-side math mirrors `pnl._open_market_and_basis()`;
    short-side math mirrors `_estimate_short_option_liability()`.
    """
    long_stock_mv = Decimal("0")
    long_option_mv = Decimal("0")
    long_cost_total = Decimal("0")

    for lot, rem_qty, rem_basis in consumed:
        if rem_qty <= 0:
            continue
        if lot.option_details is not None:
            # Long option lot — carried at cost basis (no live mark).
            # Past-expiry → skip silently (matches build_unrealized_breakdown).
            if lot.option_details.expiry < as_of:
                continue
            long_option_mv += rem_basis
            long_cost_total += rem_basis
            continue
        quote = prices.get(lot.ticker)
        if quote is None or quote.price is None:
            # No quote — carry at basis so totals reconcile with kpis.open_position_value
            # (which uses the same fallback when prices are missing for non-all-unpriced runs).
            long_stock_mv += rem_basis
            long_cost_total += rem_basis
            continue
        last = Decimal(str(quote.price))
        market = rem_qty * last
        long_stock_mv += market
        long_cost_total += rem_basis

    short_premium_total = Decimal("0")
    short_liability_total = Decimal("0")
    has_short_options = False
    for row in short_option_rows:
        if row.opened_at is None:
            continue
        has_short_options = True
        quote = prices.get(row.ticker)
        if quote is None or quote.price is None:
            # No spot quote — short liability cannot be estimated; treat as 0
            # (premium received already in cash_balance, so this errs on the
            # side of overstating account value, mirroring the unrealized
            # panel's behavior of excluding the row).
            continue
        spot = Decimal(str(quote.price))
        est_liability, *_ = _estimate_short_option_liability(row=row, spot=spot, as_of=as_of)
        short_premium_total += row.premium_received
        short_liability_total += est_liability

    long_stock_mv = long_stock_mv.quantize(Decimal("0.01"))
    long_option_mv = long_option_mv.quantize(Decimal("0.01"))
    short_liability_total = short_liability_total.quantize(Decimal("0.01"))

    # Composition: cash + long_stock + long_option − short_liability
    composition_total = (cash_balance + long_stock_mv + long_option_mv - short_liability_total).quantize(
        Decimal("0.01")
    )

    # Current unrealized = (long MV − long cost) + (short premium received − short liability)
    current_unrealized = (
        (long_stock_mv + long_option_mv - long_cost_total) + (short_premium_total - short_liability_total)
    ).quantize(Decimal("0.01"))

    # Source equation, before residual. Any remaining gap is folded into a
    # labelled "Other / unattributed" row so the panel always renders — better
    # to show the user a visible discrepancy than to 500 the whole tile.
    classified_source = (
        net_contributed
        + lifetime_realized_economic
        + non_contribution_cash_flow
        + share_transfer_basis_net
        + current_unrealized
    ).quantize(Decimal("0.01"))
    reconciliation_residual = (composition_total - classified_source).quantize(Decimal("0.01"))

    return AccountValueBreakdown(
        cash_balance=cash_balance.quantize(Decimal("0.01")),
        long_stock_mv=long_stock_mv,
        long_option_mv=long_option_mv,
        short_option_liability=short_liability_total,
        net_contributed=net_contributed.quantize(Decimal("0.01")),
        lifetime_realized_economic=lifetime_realized_economic.quantize(Decimal("0.01")),
        non_contribution_cash_flow=non_contribution_cash_flow.quantize(Decimal("0.01")),
        share_transfer_basis_net=share_transfer_basis_net.quantize(Decimal("0.01")),
        current_unrealized=current_unrealized,
        reconciliation_residual=reconciliation_residual,
        total_account_value=composition_total,
        missing_symbols=tuple(missing_symbols),
        has_short_options=has_short_options,
        fetched_at=fetched_at,
    )


@dataclass(frozen=True)
class TradeRow:
    """One trade in the 'Trades closed today' block."""

    trade_id: str
    ticker: str
    side: str  # Trade.action values (e.g., "Buy" / "Sell")
    quantity: Decimal
    realized_pnl: Decimal  # 0 for opening trades


@dataclass(frozen=True)
class MoverRow:
    """One row in the 'Top mark-to-market movers' block."""

    ticker: str
    shares: Decimal
    prev_close: Decimal
    close: Decimal
    contribution: Decimal  # shares * (close - prev_close), signed


@dataclass(frozen=True)
class CashEventRow:
    """One row in the 'Cash flow events' block."""

    account: str
    kind: str  # CashEvent.kind values (e.g., "transfer_in", "transfer_out")
    amount: Decimal  # signed: + for inflow, - for outflow


@dataclass(frozen=True)
class DividendRow:
    """One row in the 'Dividends' block."""

    ticker: str
    amount: Decimal


@dataclass(frozen=True)
class WashEventRef:
    """Reference to a wash-sale row whose sale leg is on this date.

    The renderer deep-links to the existing /tax violation explainer; we
    don't duplicate that payload here.
    """

    kind: str  # "violation" | "exempt"
    row_id: int
    ticker: str


@dataclass(frozen=True)
class EquityPointBreakdown:
    """Payload for the equity-curve click-to-explain panel.

    The four equation components (``contributions``, ``realized_pnl``,
    ``delta_unrealized``, ``dividends``) must reconcile to
    ``delta_account_value`` within tolerance; any drift is exposed as
    ``residual`` rather than silently absorbed.

    When ``is_starting_snapshot`` is True the panel is the first point in
    the filtered series and there is no previous-point delta to show.
    """

    on: dt.date
    previous_on: dt.date | None
    delta_account_value: Decimal
    contributions: Decimal
    realized_pnl: Decimal
    delta_unrealized: Decimal
    dividends: Decimal
    residual: Decimal
    trades: list[TradeRow]
    top_movers: list[MoverRow]
    cash_events: list[CashEventRow]
    dividend_events: list[DividendRow]
    wash_events: list[WashEventRef]
    unpriced_tickers: tuple[str, ...]
    unpriced_basis_total: Decimal
    is_starting_snapshot: bool
    starting_holdings_count: int
    starting_contributed_to_date: Decimal


# Mirror of brokers/schwab.py::_BUY_ACTIONS. Opening trades produce no
# realized P&L (basis sits on the new lot until it's later closed); they
# must be matched by name, not by ``startswith("buy")`` — "Reinvest" and
# "Reinvest Shares" are buys but don't start with "buy", and would
# otherwise fall through to the sell branch producing a phantom P&L.
_BUY_ACTIONS_LOWER = frozenset({"buy", "reinvest shares", "reinvest", "buy to open"})


def _trade_realized(t) -> Decimal:
    """Realized P&L for a single trade row.

    Sells: proceeds - basis. Buys: 0 (basis sits on lot, not realized).
    Mirrors the convention used across ``portfolio/pnl.py``.

    ``Trade.action`` values in this codebase are ``"Buy"`` / ``"Sell"``
    (uppercase first letter); ``Trade.proceeds`` and ``Trade.cost_basis``
    are ``float | None``.
    """
    if (t.action or "").strip().lower() in _BUY_ACTIONS_LOWER:
        return Decimal("0")
    proceeds = Decimal(str(t.proceeds)) if t.proceeds is not None else Decimal("0")
    basis = Decimal(str(t.cost_basis)) if t.cost_basis is not None else Decimal("0")
    return (proceeds - basis).quantize(Decimal("0.01"))


def _build_trade_rows(trades_on_date) -> tuple[Decimal, list[TradeRow]]:
    """Compute realized P&L total + top-5 trade rows (by |realized_pnl|)."""
    realized = sum((_trade_realized(t) for t in trades_on_date), Decimal("0"))
    rows = [
        TradeRow(
            trade_id=t.id,
            ticker=t.ticker,
            side=t.action,
            quantity=Decimal(str(t.quantity)),
            realized_pnl=_trade_realized(t),
        )
        for t in trades_on_date
    ]
    rows.sort(key=lambda r: abs(r.realized_pnl), reverse=True)
    return realized, rows[:5]


def _classify_cash_events(cash_events_on_date) -> tuple[Decimal, list[CashEventRow]]:
    """Sum signed contributions (transfer_in/_out only) + emit rows for them.

    Mirrors ``portfolio/cash_flow.py::_event_contrib_delta`` semantics — only
    ``transfer_in`` / ``transfer_out`` count as contributions in this codebase
    (dividends/interest/fees are non-contribution cash flow and are skipped).
    """
    total = Decimal("0")
    rows: list[CashEventRow] = []
    for e in cash_events_on_date:
        if e.kind == "transfer_in":
            signed = Decimal(str(e.amount))
        elif e.kind == "transfer_out":
            signed = -abs(Decimal(str(e.amount)))
        else:
            continue
        total += signed
        rows.append(CashEventRow(account=e.account, kind=e.kind, amount=signed))
    return total, rows


def _build_dividend_rows(dividend_events_on_date) -> tuple[Decimal, list[DividendRow]]:
    """Sum dividend amounts + emit one row per event."""
    total = Decimal("0")
    rows: list[DividendRow] = []
    for d in dividend_events_on_date:
        amt = Decimal(str(d.amount))
        total += amt
        rows.append(DividendRow(ticker=d.ticker or "(cash)", amount=amt))
    return total, rows


def _compute_mtm_movers(
    open_lots_prev_day,
    previous_on: dt.date,
    on: dt.date,
    get_close: Callable[[str, dt.date], Decimal | None],
) -> tuple[Decimal, list[MoverRow], tuple[str, ...], Decimal]:
    """Aggregate lots per ticker, compute MTM delta and top-5 movers.

    Returns ``(delta_unrealized, top5_movers, unpriced_tickers_sorted,
    unpriced_basis_total)``. Tickers missing either prev or current close
    contribute 0 to ``delta_unrealized`` and surface in ``unpriced_tickers``.
    """
    shares_by_ticker: dict[str, Decimal] = {}
    basis_by_ticker: dict[str, Decimal] = {}
    for lot in open_lots_prev_day:
        qty = Decimal(str(lot.quantity))
        basis = Decimal(str(lot.adjusted_basis))
        shares_by_ticker[lot.ticker] = shares_by_ticker.get(lot.ticker, Decimal("0")) + qty
        basis_by_ticker[lot.ticker] = basis_by_ticker.get(lot.ticker, Decimal("0")) + basis

    movers: list[MoverRow] = []
    delta_unrealized = Decimal("0")
    unpriced: list[str] = []
    unpriced_basis = Decimal("0")
    for ticker, shares in shares_by_ticker.items():
        prev_c = get_close(ticker, previous_on)
        cur_c = get_close(ticker, on)
        if prev_c is None or cur_c is None:
            unpriced.append(ticker)
            unpriced_basis += basis_by_ticker[ticker]
            continue
        prev_c_d = Decimal(str(prev_c))
        cur_c_d = Decimal(str(cur_c))
        contrib = (shares * (cur_c_d - prev_c_d)).quantize(Decimal("0.01"))
        delta_unrealized += contrib
        movers.append(
            MoverRow(
                ticker=ticker,
                shares=shares,
                prev_close=prev_c_d,
                close=cur_c_d,
                contribution=contrib,
            )
        )

    movers.sort(key=lambda m: abs(m.contribution), reverse=True)
    return delta_unrealized, movers[:5], tuple(sorted(unpriced)), unpriced_basis


def _collect_wash_refs(violations_on_date, exempt_matches_on_date) -> list[WashEventRef]:
    """Collect wash-sale refs (violations + exempt matches) for deep-linking.

    The renderer deep-links to the existing ``/tax`` violation/exempt explainer
    fragments, so we only carry id+ticker. ``WashSaleViolation.id`` is a
    UUID-shaped string by default; route handlers typically pass DB-backed
    rows whose ``id`` is a stable int. Coerce defensively. ``ExemptMatch``
    has no ``id`` field in the domain model (DB rows do); fall back to 0.
    """
    refs: list[WashEventRef] = []
    for v in violations_on_date:
        try:
            row_id = int(v.id)
        except (TypeError, ValueError):
            row_id = 0
        refs.append(WashEventRef(kind="violation", row_id=row_id, ticker=v.ticker))
    for em in exempt_matches_on_date:
        raw = getattr(em, "id", 0)
        try:
            row_id = int(raw)
        except (TypeError, ValueError):
            row_id = 0
        refs.append(WashEventRef(kind="exempt", row_id=row_id, ticker=em.ticker))
    return refs


def build_equity_point_breakdown(
    *,
    on: dt.date,
    previous_on: dt.date | None,
    trades_on_date: list,
    cash_events_on_date: list,
    dividend_events_on_date: list,
    open_lots_prev_day: list,
    violations_on_date: list,
    exempt_matches_on_date: list,
    get_close: Callable[[str, dt.date], Decimal | None],
    delta_account_value: Decimal,
    starting_contributed_to_date: Decimal = Decimal("0"),
) -> EquityPointBreakdown:
    """Decompose the equity-curve point-to-point delta into its sources.

    See ``docs/superpowers/specs/2026-05-16-equity-curve-click-to-explain-design.md``.

    Caller is responsible for filtering inputs by account; this function
    is account-agnostic and just sums what it's given.
    """
    # Starting-snapshot case — first point in the filtered series has no
    # previous-point delta to compare against. Surface a "where the user
    # started" panel instead (ticker count + cumulative contributions).
    if previous_on is None:
        return EquityPointBreakdown(
            on=on,
            previous_on=None,
            delta_account_value=Decimal("0"),
            contributions=Decimal("0"),
            realized_pnl=Decimal("0"),
            delta_unrealized=Decimal("0"),
            dividends=Decimal("0"),
            residual=Decimal("0"),
            trades=[],
            top_movers=[],
            cash_events=[],
            dividend_events=[],
            wash_events=[],
            unpriced_tickers=(),
            unpriced_basis_total=Decimal("0"),
            is_starting_snapshot=True,
            starting_holdings_count=len({lot.ticker for lot in open_lots_prev_day}),
            starting_contributed_to_date=starting_contributed_to_date,
        )

    realized, trade_rows = _build_trade_rows(trades_on_date)
    contributions, cash_event_rows = _classify_cash_events(cash_events_on_date)
    dividends_total, dividend_rows = _build_dividend_rows(dividend_events_on_date)
    delta_unrealized, movers, unpriced, unpriced_basis = _compute_mtm_movers(
        open_lots_prev_day, previous_on, on, get_close
    )
    wash_events = _collect_wash_refs(violations_on_date, exempt_matches_on_date)

    residual = (delta_account_value - (contributions + realized + delta_unrealized + dividends_total)).quantize(
        Decimal("0.01")
    )

    return EquityPointBreakdown(
        on=on,
        previous_on=previous_on,
        delta_account_value=delta_account_value,
        contributions=contributions,
        realized_pnl=realized,
        delta_unrealized=delta_unrealized,
        dividends=dividends_total,
        residual=residual,
        trades=trade_rows,
        top_movers=movers,
        cash_events=cash_event_rows,
        dividend_events=dividend_rows,
        wash_events=wash_events,
        unpriced_tickers=unpriced,
        unpriced_basis_total=unpriced_basis,
        is_starting_snapshot=False,
        starting_holdings_count=0,
        starting_contributed_to_date=Decimal("0"),
    )
