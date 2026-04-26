"""KPI aggregations for the Portfolio page header.

period: (year_start_inclusive, year_end_exclusive), e.g. (2026, 2027) for YTD 2026,
or None for "Lifetime" (no period filter).
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from net_alpha.models.domain import Lot, Trade, WashSaleViolation
from net_alpha.portfolio.models import KpiSet, WashImpact
from net_alpha.pricing.provider import Quote


def _realized_in(trades: Iterable[Trade], period: tuple[int, int] | None) -> Decimal:
    total = Decimal("0")
    for t in trades:
        if t.action.lower() != "sell":
            continue
        if period is not None and not (period[0] <= t.date.year < period[1]):
            continue
        total += Decimal(str((t.proceeds or 0) - (t.cost_basis or 0)))
    return total


def _open_market_and_basis(
    lots: Iterable[Lot],
    prices: dict[str, Quote],
) -> tuple[Decimal, Decimal, tuple[str, ...]]:
    """Return (priced_market, priced_basis, missing_symbols).

    priced_market = Σ(qty × price) over equity lots that have a quote.
    priced_basis  = Σ(adjusted_basis) over the SAME priced lots.
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
    for lot in lots:
        if lot.option_details is not None:
            continue  # equity-only for KPI market value
        quote = prices.get(lot.ticker)
        if quote is None:
            missing.add(lot.ticker)
            continue
        total_value += Decimal(str(lot.quantity)) * quote.price
        priced_basis += Decimal(str(lot.adjusted_basis))  # NOTE: adjusted_basis is total, not per-share
    return total_value, priced_basis, tuple(sorted(missing))


def compute_kpis(
    *,
    trades: Iterable[Trade],
    lots: Iterable[Lot],
    prices: dict[str, Quote],
    period_label: str,
    period: tuple[int, int] | None,
    account: str | None,
) -> KpiSet:
    trades = list(trades)
    lots = list(lots)
    if account:
        trades = [t for t in trades if t.account == account]
        lots = [lot for lot in lots if lot.account == account]

    period_realized = _realized_in(trades, period)
    lifetime_realized = _realized_in(trades, None)

    market, basis, missing = _open_market_and_basis(lots, prices)
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

    return KpiSet(
        period_label=period_label,
        period_realized=period_realized,
        period_unrealized=period_unrealized,
        lifetime_realized=lifetime_realized,
        lifetime_unrealized=lifetime_unrealized,
        open_position_value=open_value,
        lifetime_net_pl=lifetime_net_pl,
        missing_symbols=missing,
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
