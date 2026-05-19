"""Monthly realized-P&L aggregation for the calendar dual-ribbon view."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from decimal import Decimal

from net_alpha.models.domain import Trade
from net_alpha.portfolio.models import MonthlyPnl, MonthlyPnlPoint
from net_alpha.portfolio.pnl import realized_pl_contributions


def monthly_realized_pl(
    *,
    trades: Iterable[Trade],
    year: int,
    ticker: str | None,
    accounts: Sequence[str] | None = None,
) -> list[MonthlyPnl]:
    """Return 12 MonthlyPnl rows (Jan..Dec) of realized P&L for `year`.

    Delegates per-row P&L attribution to ``realized_pl_contributions`` so
    short-option Buy-to-Close trades (``option_short_close`` /
    ``..._expiry``) are included with proper STO pairing — otherwise the
    heatmap would diverge from the headline Realized P&L KPI on the same
    page. Filters by ticker and account after attribution.
    """
    _filter = set(accounts) if accounts else None
    buckets: dict[int, dict[str, Decimal | int]] = {
        m: {"gain": Decimal("0"), "loss": Decimal("0"), "count": 0} for m in range(1, 13)
    }

    # Equity Sells with missing proceeds/cost_basis are degenerate — drop
    # them so they don't pollute the monthly P&L. STOs (option Sells) are
    # kept regardless of cost_basis=None because ``realized_pl_contributions``
    # needs them to pair against their closing BTCs.
    def _keep(t: Trade) -> bool:
        if t.action.lower() == "sell" and t.option_details is None:
            return t.proceeds is not None and t.cost_basis is not None
        return True

    contributions = realized_pl_contributions([t for t in trades if _keep(t)], period=(year, year + 1))
    for c in contributions:
        if c.date.year != year:
            continue
        if ticker is not None and c.ticker != ticker:
            continue
        if _filter is not None and c.account not in _filter:
            continue
        bucket = buckets[c.date.month]
        if c.amount >= 0:
            bucket["gain"] += c.amount
        else:
            bucket["loss"] += -c.amount
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
    accounts: Sequence[str] | None = None,
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
            accounts=accounts,
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


_MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _month_label(p: MonthlyPnlPoint) -> str:
    return f"{_MONTH_ABBR[p.month - 1]} {p.year}"


def monthly_pl_lifetime_stats(
    points: Sequence[MonthlyPnlPoint],
) -> tuple[Decimal, Decimal, str, Decimal, str] | None:
    """Return (avg, best, best_label, worst, worst_label) over a monthly P&L
    series. Ties: earliest month wins (preserves chronological reading).

    Returns ``None`` when the input is empty. ``avg`` is the simple mean of
    ``net_pl`` over all months in the series, including zero-P&L months
    (lifetime-mean intent). Labels are formatted ``"Mon YYYY"``.
    """
    if not points:
        return None
    total = sum((p.net_pl for p in points), start=Decimal("0"))
    avg = total / Decimal(len(points))
    best = max(points, key=lambda p: (p.net_pl, -p.year * 12 - p.month))
    worst = min(points, key=lambda p: (p.net_pl, p.year * 12 + p.month))
    return avg, best.net_pl, _month_label(best), worst.net_pl, _month_label(worst)
