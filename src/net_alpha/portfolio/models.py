"""Portfolio view models.

These are the renderer-facing shapes returned by the portfolio.* compute
functions. They are NOT persisted — recomputed on each request.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class PositionRow:
    symbol: str
    accounts: tuple[str, ...]
    qty: Decimal
    market_value: Decimal | None  # None when no price is available
    open_cost: Decimal  # sum of adjusted_basis across open lots
    avg_basis: Decimal  # open_cost / qty (formula C)
    cash_sunk_per_share: Decimal  # (buys − sells − option_premium) / qty (formula A)
    realized_pl: Decimal  # period-scoped
    unrealized_pl: Decimal | None  # None when no price


@dataclass(frozen=True)
class KpiSet:
    period_label: str
    period_realized: Decimal
    period_unrealized: Decimal | None
    lifetime_realized: Decimal
    lifetime_unrealized: Decimal | None
    open_position_value: Decimal | None
    lifetime_net_pl: Decimal | None  # realized + unrealized; None when prices unavailable
    missing_symbols: tuple[str, ...] = ()  # tickers without a quote — affected KPIs are partial sums


@dataclass(frozen=True)
class TreemapTile:
    symbol: str  # "OTHER" used for the long-tail aggregate tile
    market_value: Decimal
    unrealized_pl: Decimal | None
    x_pct: float  # 0–100, percent of container width
    y_pct: float
    width_pct: float
    height_pct: float


@dataclass(frozen=True)
class EquityPoint:
    on: date
    cumulative_realized: Decimal
    unrealized: Decimal | None  # only on the present-day point


@dataclass(frozen=True)
class WashImpact:
    period_label: str
    disallowed_total: Decimal
    violation_count: int
    confirmed_count: int
    probable_count: int
    unclear_count: int


@dataclass(frozen=True)
class AgingLot:
    symbol: str
    account: str
    qty: Decimal
    acquired_on: date
    days_to_ltcg: int  # negative if already long-term (excluded by callers)


@dataclass(frozen=True)
class MonthlyPnl:
    """One month's realized P&L for the calendar P&L ribbon."""

    month: int  # 1..12
    net_pl: Decimal  # gain - loss
    gross_gain: Decimal  # sum of positive sell P&L
    gross_loss: Decimal  # sum of |negative sell P&L| (positive number)
    trade_count: int  # number of sell trades contributing
