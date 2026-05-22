"""Month-end equity tile grid for the Portfolio overview.

Computes one MonthEndEquityTile per calendar month of a given year, using
the existing ``account_value_at`` (level) and ``monthly_realized_pl``
(flow) aggregators. Pure function — caller is responsible for pre-scoping
trades/lots/cash_points by Account, exactly as the rest of ``portfolio/``.
"""

from __future__ import annotations

import datetime as dt
from calendar import monthrange
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from net_alpha.models.domain import Lot, Trade
from net_alpha.portfolio.account_value import account_value_at
from net_alpha.portfolio.models import CashBalancePoint, MonthlyPnl

_MONTH_ABBR: tuple[str, ...] = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


@dataclass(frozen=True)
class MonthEndEquityTile:
    month: int
    label: str
    end_value: Decimal | None
    mom_delta_pct: Decimal | None
    mv_delta: Decimal | None
    cash_delta: Decimal | None
    realized_pl: Decimal | None
    is_current: bool
    is_future: bool


def _cash_at(cash_points: Sequence[CashBalancePoint], on: dt.date) -> Decimal | None:
    """Most recent cash_balance with ``cp.on <= on``, or None if none qualify.

    Requires *cash_points* to be sorted ascending by ``on``.
    """
    latest: Decimal | None = None
    for cp in cash_points:
        if cp.on <= on:
            latest = cp.cash_balance
        else:
            break
    return latest


def month_end_equity_series(
    *,
    year: int,
    today: dt.date,
    trades: Sequence[Trade],
    lots: Sequence[Lot],
    cash_points: Sequence[CashBalancePoint],
    get_close: Callable[[str, dt.date], Decimal | None],
    monthly_realized: Sequence[MonthlyPnl],
) -> list[MonthEndEquityTile]:
    """Return 12 tiles for ``year`` in calendar order.

    For each month *m*:
    - ``end_value`` = ``account_value_at(date)`` where ``date`` is the last
      calendar day of *m*, or ``today`` when *m* is the current month of the
      current year. account_value_at already forward-fills weekend/holiday
      closes up to 7 days.
    - ``end_value`` is None when there is no cash history at or before that
      date (we distinguish this from "$0 balance" by checking cash_points).
    - ``is_current`` is True only for the current month of the current year
      AND only when end_value is not None.
    - ``is_future`` is True for months strictly after today.month in the
      current year; never True for historical years.
    - ``mom_delta_pct`` is the % change vs the prior month's end_value,
      carried forward across None gaps.
    - ``mv_delta`` / ``cash_delta`` are absolute Decimal changes for tooltip.
    - ``realized_pl`` is sourced from ``monthly_realized`` rows (net_pl).
    """
    is_current_year = year == today.year
    # Materialize and sort cash points once — _cash_at relies on sorted order;
    # account_value_at takes lists and we'd otherwise allocate per iteration.
    trades_list = list(trades)
    lots_list = list(lots)
    cash_list = sorted(cash_points, key=lambda p: p.on)
    first_cash = min((p.on for p in cash_list), default=None)

    # Build month → realized P&L lookup once.
    realized_by_month: dict[int, Decimal] = {row.month: row.net_pl for row in monthly_realized}

    # Prior-month state, carried forward across None gaps.
    prior_end: Decimal | None = None
    prior_cash: Decimal | None = None
    prior_holdings: Decimal | None = None

    # Seed prior_* from the last cash point that falls before the year starts
    # (i.e. the Dec 31 of the previous year if present), so Jan can compute
    # deltas against the year-opening balance.
    year_start = dt.date(year, 1, 1)
    prior_cash = _cash_at(cash_list, year_start - dt.timedelta(days=1))
    if prior_cash is not None and first_cash is not None and year_start > first_cash:
        prior_end = account_value_at(
            on=year_start - dt.timedelta(days=1),
            trades=trades_list,
            lots=lots_list,
            cash_points=cash_list,
            get_close=get_close,
        )
        prior_holdings = prior_end - prior_cash if prior_end is not None else None

    tiles: list[MonthEndEquityTile] = []
    for m in range(1, 13):
        is_future = is_current_year and m > today.month
        if is_current_year and m == today.month:
            sample_date = today
        else:
            _, last_day = monthrange(year, m)
            sample_date = dt.date(year, m, last_day)

        if is_future or first_cash is None or sample_date < first_cash:
            end_value: Decimal | None = None
        else:
            end_value = account_value_at(
                on=sample_date,
                trades=trades_list,
                lots=lots_list,
                cash_points=cash_list,
                get_close=get_close,
            )

        is_current = is_current_year and m == today.month and end_value is not None

        # Derived breakdown fields — only when we have real data this month.
        cash_at: Decimal | None = None
        holdings_at: Decimal | None = None
        mom_delta_pct: Decimal | None = None
        mv_delta: Decimal | None = None
        cash_delta: Decimal | None = None
        realized_pl: Decimal | None = None

        if not is_future:
            realized_pl = realized_by_month.get(m)

        if end_value is not None:
            cash_at = _cash_at(cash_list, sample_date)
            if cash_at is not None:
                holdings_at = end_value - cash_at

            if prior_end is not None and prior_end != Decimal("0"):
                mom_delta_pct = ((end_value - prior_end) / prior_end * Decimal("100")).quantize(Decimal("0.01"))

            if holdings_at is not None and prior_holdings is not None:
                mv_delta = holdings_at - prior_holdings

            if cash_at is not None and prior_cash is not None:
                cash_delta = cash_at - prior_cash

        # Carry prior_* forward (across None gaps).
        prior_end = end_value if end_value is not None else prior_end
        prior_cash = cash_at if cash_at is not None else prior_cash
        prior_holdings = holdings_at if holdings_at is not None else prior_holdings

        tiles.append(
            MonthEndEquityTile(
                month=m,
                label=_MONTH_ABBR[m - 1],
                end_value=end_value,
                mom_delta_pct=mom_delta_pct,
                mv_delta=mv_delta,
                cash_delta=cash_delta,
                realized_pl=realized_pl,
                is_current=is_current,
                is_future=is_future,
            )
        )
    return tiles


def month_end_equity_summary(
    tiles: Sequence[MonthEndEquityTile],
    *,
    today: dt.date,
    prior_year_end_value: Decimal | None,
) -> dict[str, Decimal | str | None] | None:
    """Footer-caption summary over a year's tiles.

    Args:
        tiles: 12 tiles from ``month_end_equity_series``.
        today: needed only for excluding the current partial month from
            best/worst (the tile already carries ``is_current``).
        prior_year_end_value: end-of-prior-year account value, used as the
            YTD anchor. When None, ytd_delta_abs / ytd_delta_pct are omitted.

    Returns ``None`` when no tile has data. Otherwise returns:

    - ``ytd_delta_abs``: latest_completed.end_value − prior_year_end_value
      (None when ``prior_year_end_value`` is None).
    - ``ytd_delta_pct``: ytd_delta_abs / prior_year_end_value × 100
      (None when anchor is None or 0).
    - ``best_month_label`` / ``best_month_delta_pct``: completed month with
      the largest ``mom_delta_pct`` (ties: earliest wins).
    - ``worst_month_label`` / ``worst_month_delta_pct``: completed month
      with the smallest ``mom_delta_pct``.

    "Completed" = ``end_value is not None`` AND NOT ``is_current``. If only
    the current partial month has data, it's treated as completed for the
    purpose of populating best/worst.
    """
    completed = [t for t in tiles if t.end_value is not None and not t.is_current]
    if not completed:
        with_value = [t for t in tiles if t.end_value is not None]
        if not with_value:
            return None
        completed = with_value

    latest = completed[-1]

    if prior_year_end_value is None:
        ytd_delta_abs: Decimal | None = None
        ytd_delta_pct: Decimal | None = None
    else:
        ytd_delta_abs = (latest.end_value - prior_year_end_value).quantize(Decimal("0.01"))
        ytd_delta_pct = (
            (ytd_delta_abs / prior_year_end_value * Decimal("100")).quantize(Decimal("0.01"))
            if prior_year_end_value != Decimal("0")
            else None
        )

    ranked = [t for t in completed if t.mom_delta_pct is not None]
    if not ranked:
        ranked = completed
    best = max(ranked, key=lambda t: t.mom_delta_pct or Decimal("-Infinity"))
    worst = min(ranked, key=lambda t: t.mom_delta_pct or Decimal("Infinity"))

    return {
        "ytd_delta_abs": ytd_delta_abs,
        "ytd_delta_pct": ytd_delta_pct,
        "best_month_label": best.label,
        "best_month_delta_pct": best.mom_delta_pct,
        "worst_month_label": worst.label,
        "worst_month_delta_pct": worst.mom_delta_pct,
    }
