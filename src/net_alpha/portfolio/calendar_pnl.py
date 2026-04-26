"""Monthly realized-P&L aggregation for the calendar dual-ribbon view."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from net_alpha.models.domain import Trade
from net_alpha.portfolio.models import MonthlyPnl


def monthly_realized_pl(
    *,
    trades: Iterable[Trade],
    year: int,
    ticker: str | None,
    account: str | None,
) -> list[MonthlyPnl]:
    """Return 12 MonthlyPnl rows (Jan..Dec) of realized sell P&L for `year`.

    Filters: trades not in `year`, not Sell, missing proceeds/cost, mismatching
    ticker, or mismatching account are excluded.
    """
    buckets: dict[int, dict[str, Decimal | int]] = {
        m: {"gain": Decimal("0"), "loss": Decimal("0"), "count": 0} for m in range(1, 13)
    }
    for t in trades:
        if t.date.year != year:
            continue
        if t.action.lower() != "sell":
            continue
        if t.proceeds is None or t.cost_basis is None:
            continue
        if ticker is not None and t.ticker != ticker:
            continue
        if account is not None and t.account != account:
            continue
        pl = Decimal(str(t.proceeds)) - Decimal(str(t.cost_basis))
        bucket = buckets[t.date.month]
        if pl >= 0:
            bucket["gain"] += pl
        else:
            bucket["loss"] += -pl
        bucket["count"] += 1
    return [
        MonthlyPnl(
            month=m,
            net_pl=buckets[m]["gain"] - buckets[m]["loss"],
            gross_gain=buckets[m]["gain"],
            gross_loss=buckets[m]["loss"],
            trade_count=int(buckets[m]["count"]),
        )
        for m in range(1, 13)
    ]
