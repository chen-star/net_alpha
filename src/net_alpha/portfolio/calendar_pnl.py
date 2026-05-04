"""Monthly realized-P&L aggregation for the calendar dual-ribbon view."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from net_alpha.models.domain import Trade
from net_alpha.portfolio.models import MonthlyPnl, MonthlyPnlPoint


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


def monthly_realized_pl_series(
    *,
    trades: Iterable[Trade],
    period: tuple[int, int] | None,
    account: str | None,
    today: date,
) -> list[MonthlyPnlPoint]:
    """Return a chronological list of monthly realized-P&L points.

    The Portfolio overview's wide bar chart calls this with the page's
    selected Period:

    - ``period=(start_year, end_year_exclusive)`` with ``start_year == today.year``
      → YTD scope: Jan..today.month (no future months).
    - ``period=(year, year+1)`` with ``year < today.year``
      → historical single year: full Jan..Dec.
    - ``period=None`` → Lifetime: every month from January of
      ``min(trade.date.year)`` through ``today.month`` of ``today.year``,
      gap-filled with zero months across years that have no closes. Returns
      ``[]`` when ``trades`` contains no trades at all (no axis to draw).

    The wash-sale-disallowed-loss add-back already happened upstream during
    engine recompute (see ``WashSaleViolation.disallowed_loss``) — this
    function just sums recognized realized P&L straight from
    ``proceeds - cost_basis`` on Sell rows, exactly as
    ``monthly_realized_pl`` does.
    """
    # Materialize once: we may iterate multiple times (per-year scoping in the
    # Lifetime branch) and Iterable[Trade] makes no such guarantee.
    trade_list = list(trades)

    def _year_points(year: int, *, max_month: int = 12) -> list[MonthlyPnlPoint]:
        """Wrap one year of monthly_realized_pl output as MonthlyPnlPoints,
        truncated to ``max_month`` (inclusive)."""
        rows = monthly_realized_pl(
            trades=trade_list,
            year=year,
            ticker=None,
            account=account,
        )
        return [
            MonthlyPnlPoint(
                year=year,
                month=row.month,
                net_pl=row.net_pl,
                gross_gain=row.gross_gain,
                gross_loss=row.gross_loss,
                trade_count=row.trade_count,
            )
            for row in rows
            if row.month <= max_month
        ]

    if period is not None:
        year = period[0]
        max_month = today.month if year == today.year else 12
        return _year_points(year, max_month=max_month)

    # Lifetime: walk first-trade-year through today.year inclusive. With no
    # trades there is no axis to draw — returning an empty list lets the
    # template fall through to its empty state.
    trade_years = [t.date.year for t in trade_list]
    if not trade_years:
        return []
    start_year = min(trade_years)
    end_year = today.year
    out: list[MonthlyPnlPoint] = []
    for year in range(start_year, end_year + 1):
        max_month = today.month if year == end_year else 12
        out.extend(_year_points(year, max_month=max_month))
    return out
