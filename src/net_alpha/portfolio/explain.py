"""Pure-function builders for the math-explainer panels on Total Return
and Unrealized P/L KPI tiles. No I/O. The web layer wires repo + pricing
data in; this module returns dataclasses ready for Jinja.
"""

from __future__ import annotations

import datetime as dt
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
                 + current_unrealized

    The reconciliation invariant is enforced in `build_account_value_breakdown`.
    `lifetime_realized_economic` MUST be the wash-adjusted economic figure
    (`KpiSet.lifetime_realized_economic`), not the tax-recognized one — the
    cash account never sees a wash-sale disallowance.
    """

    # Composition (Equation 1)
    cash_balance: Decimal
    long_stock_mv: Decimal
    long_option_mv: Decimal
    short_option_liability: Decimal     # positive number, subtracted in the equation
    # Source (Equation 2)
    net_contributed: Decimal
    lifetime_realized_economic: Decimal
    current_unrealized: Decimal
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
    premium_per_share = (
        row.premium_received / contracts / multiplier if contracts > 0 else Decimal("0")
    )
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
    consumed: list,            # list[(Lot, Decimal rem_qty, Decimal rem_basis)]
    short_option_rows: list,   # list[OpenShortOptionRow]
    prices: dict,              # {ticker: Quote}
    cash_balance: Decimal,
    net_contributed: Decimal,
    lifetime_realized_economic: Decimal,
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
        est_liability, *_ = _estimate_short_option_liability(
            row=row, spot=spot, as_of=as_of
        )
        short_premium_total += row.premium_received
        short_liability_total += est_liability

    long_stock_mv = long_stock_mv.quantize(Decimal("0.01"))
    long_option_mv = long_option_mv.quantize(Decimal("0.01"))
    short_liability_total = short_liability_total.quantize(Decimal("0.01"))

    # Composition: cash + long_stock + long_option − short_liability
    composition_total = (
        cash_balance + long_stock_mv + long_option_mv - short_liability_total
    ).quantize(Decimal("0.01"))

    # Current unrealized = (long MV − long cost) + (short premium received − short liability)
    current_unrealized = (
        (long_stock_mv + long_option_mv - long_cost_total)
        + (short_premium_total - short_liability_total)
    ).quantize(Decimal("0.01"))

    # Source: net_contributed + lifetime_realized_economic + current_unrealized
    source_total = (
        net_contributed + lifetime_realized_economic + current_unrealized
    ).quantize(Decimal("0.01"))

    # Reconciliation invariant — both equations must agree to within $0.01.
    if abs(composition_total - source_total) > Decimal("0.01"):
        raise ValueError(
            f"AccountValueBreakdown reconciliation failed: "
            f"composition={composition_total} source={source_total}"
        )

    return AccountValueBreakdown(
        cash_balance=cash_balance.quantize(Decimal("0.01")),
        long_stock_mv=long_stock_mv,
        long_option_mv=long_option_mv,
        short_option_liability=short_liability_total,
        net_contributed=net_contributed.quantize(Decimal("0.01")),
        lifetime_realized_economic=lifetime_realized_economic.quantize(Decimal("0.01")),
        current_unrealized=current_unrealized,
        total_account_value=composition_total,
        missing_symbols=tuple(missing_symbols),
        has_short_options=has_short_options,
        fetched_at=fetched_at,
    )
