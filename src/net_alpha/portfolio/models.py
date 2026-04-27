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
class EquityPoint:
    on: date
    cumulative_realized: Decimal
    unrealized: Decimal | None  # only on the present-day point
    # Total P&L (realized + present unrealized). Plotted on the equity curve as
    # a parallel "total" series so the gap between the two lines visualizes the
    # unrealized component. None when no price data is available.
    total_pl: Decimal | None = None


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


@dataclass(frozen=True)
class AllocationSlice:
    """One ranked holding for the donut + leaderboard module."""

    rank: int  # 1-based; 0 reserved for "rest" aggregate
    symbol: str  # "OTHER" for the rest aggregate
    market_value: Decimal
    pct: Decimal  # 0..100, of total market value
    is_rest: bool


@dataclass(frozen=True)
class AllocationView:
    total_market_value: Decimal
    symbol_count: int
    slices: tuple[AllocationSlice, ...]  # length = top_n + (1 if rest else 0)
    top1_pct: Decimal
    top3_pct: Decimal
    top5_pct: Decimal
    top10_pct: Decimal


@dataclass(frozen=True)
class LossCloseRow:
    """One symbol's recent loss close — input for the home-page wash-sale watch panel."""

    symbol: str
    account: str  # the account on the most recent loss close in window
    close_date: date
    days_since: int  # today - close_date, in days
    days_to_safe: int  # window_days - days_since, clamped to >= 0
    loss_amount: Decimal  # positive number, sum of |negative realized P/L| in window for this symbol


@dataclass(frozen=True)
class CashBalancePoint:
    """One point in the cash balance series (one per distinct event date)."""

    on: date
    cash_balance: Decimal
    cumulative_contributions: Decimal


@dataclass(frozen=True)
class CashFlowKPIs:
    """Single-shot summary used by the Portfolio KPI strip."""

    cash_balance: Decimal
    net_contributions: Decimal
    holdings_value: Decimal
    account_value: Decimal
    growth: Decimal
    growth_pct: Decimal | None  # None when net_contributions == 0
    cash_share_pct: Decimal
