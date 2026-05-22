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
    """
    is_current_year = year == today.year
    sorted_cash = sorted(cash_points, key=lambda p: p.on)
    first_cash = sorted_cash[0].on if sorted_cash else None

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
                trades=list(trades),
                lots=list(lots),
                cash_points=list(cash_points),
                get_close=get_close,
            )

        is_current = is_current_year and m == today.month and end_value is not None

        tiles.append(
            MonthEndEquityTile(
                month=m,
                label=_MONTH_ABBR[m - 1],
                end_value=end_value,
                mom_delta_pct=None,
                mv_delta=None,
                cash_delta=None,
                realized_pl=None,
                is_current=is_current,
                is_future=is_future,
            )
        )
    return tiles
