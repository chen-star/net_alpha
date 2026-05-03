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
    """

    period_label: str
    ending_value: Decimal
    starting_value: Decimal
    contributions: Decimal
    total_return: Decimal
    realized_in_period: Decimal
    delta_unrealized_residual: Decimal
    is_lifetime: bool


@dataclass(frozen=True)
class UnrealizedLongLine:
    """One row in the long stock/option section of the unrealized panel."""

    symbol: str            # e.g. "AAPL" or "AAPL 180C 2026-06-20"
    qty: Decimal
    last_price: Decimal    # for long options without a quote, 0 (carried at basis)
    cost_basis: Decimal
    unrealized: Decimal


@dataclass(frozen=True)
class UnrealizedShortOptionLine:
    """One row in the short options section. Includes intermediate values
    so the renderer can show the user how the estimate was built."""

    symbol_display: str          # e.g. "SPY 500P 2026-06-20"
    contracts: int               # |qty short|
    premium_received: Decimal    # positive
    spot: Decimal
    intrinsic_per_share: Decimal
    days_total: int
    days_remaining: int
    time_value_per_share: Decimal
    est_value_to_close: Decimal  # total liability across all contracts
    unrealized: Decimal          # premium_received - est_value_to_close
    is_covered: bool             # True for calls (covered call notation)


@dataclass(frozen=True)
class UnrealizedBreakdown:
    """Payload for the Unrealized P/L explainer panel."""

    long_lines: list[UnrealizedLongLine]
    long_subtotal: Decimal
    short_option_lines: list[UnrealizedShortOptionLine]
    short_subtotal: Decimal
    total_unrealized: Decimal
    excluded_count: int  # lots/shorts skipped because no quote available


def build_total_return_breakdown(
    *,
    period_label: str,
    ending_value: Decimal,
    starting_value: Decimal,
    contributions: Decimal,
    realized_in_period: Decimal,
    is_lifetime: bool,
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
    )


def build_unrealized_breakdown(
    *,
    consumed: list,           # list[(Lot, Decimal rem_qty, Decimal rem_basis)]
    short_option_rows: list,  # list[OpenShortOptionRow]
    prices: dict,             # {ticker: Quote}
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
    short_subtotal = Decimal("0")
    excluded = 0

    for lot, rem_qty, rem_basis in consumed:
        if rem_qty <= 0:
            continue
        if lot.option_details is not None:
            # Long option lot. Past-expiry → skip silently. Otherwise carried
            # at basis (market = basis → unrealized = 0).
            if lot.option_details.expiry < as_of:
                continue
            opt = lot.option_details
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
        unrealized = (row.premium_received - est_liability).quantize(Decimal("0.01"))
        short_subtotal += unrealized
        short_lines.append(
            UnrealizedShortOptionLine(
                symbol_display=f"{row.ticker} {strike}{row.call_put} {row.expiry.isoformat()}",
                contracts=int(contracts),
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
        long_subtotal=long_subtotal,
        short_option_lines=short_lines,
        short_subtotal=short_subtotal,
        total_unrealized=long_subtotal + short_subtotal,
        excluded_count=excluded,
    )
