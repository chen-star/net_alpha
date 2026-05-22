"""Month-end equity tile grid for the Portfolio overview.

Computes one MonthEndEquityTile per calendar month of a given year, using
the existing ``account_value_at`` (level) and ``monthly_realized_pl``
(flow) aggregators. Pure function — caller is responsible for pre-scoping
trades/lots/cash_points by Account, exactly as the rest of ``portfolio/``.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from net_alpha.models.domain import Lot, Trade
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
    """Return 12 tiles for ``year`` in calendar order."""
    is_current_year = year == today.year
    tiles: list[MonthEndEquityTile] = []
    for m in range(1, 13):
        is_future = is_current_year and m > today.month
        tiles.append(
            MonthEndEquityTile(
                month=m,
                label=_MONTH_ABBR[m - 1],
                end_value=None,
                mom_delta_pct=None,
                mv_delta=None,
                cash_delta=None,
                realized_pl=None,
                is_current=False,
                is_future=is_future,
            )
        )
    return tiles
