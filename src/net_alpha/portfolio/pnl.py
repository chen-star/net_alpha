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
) -> tuple[Decimal | None, Decimal]:
    """Return (sum(qty × price), sum(adjusted_basis)) or (None, basis) when any lot is unpriced."""
    total_value: Decimal = Decimal("0")
    total_basis: Decimal = Decimal("0")
    any_missing = False
    for lot in lots:
        if lot.option_details is not None:
            continue  # equity-only for KPI market value
        qty = Decimal(str(lot.quantity))
        total_basis += Decimal(str(lot.adjusted_basis))  # NOTE: adjusted_basis is total, not per-share
        quote = prices.get(lot.ticker)
        if quote is None:
            any_missing = True
            continue
        total_value += qty * quote.price
    return (None if any_missing else total_value, total_basis)


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

    market, basis = _open_market_and_basis(lots, prices)
    if market is None:
        period_unrealized = None
        lifetime_unrealized = None
        open_value = None
    else:
        unrealized = market - basis
        period_unrealized = unrealized  # unrealized is "now"; period only relabels the card
        lifetime_unrealized = unrealized
        open_value = market

    return KpiSet(
        period_label=period_label,
        period_realized=period_realized,
        period_unrealized=period_unrealized,
        lifetime_realized=lifetime_realized,
        lifetime_unrealized=lifetime_unrealized,
        open_position_value=open_value,
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
