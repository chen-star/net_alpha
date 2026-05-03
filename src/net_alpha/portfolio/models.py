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
    # Sum of |net_qty| across all open option contracts on this underlying
    # (long + short, all strikes/expiries). Drives the "X open opt" badge in
    # the holdings table so a ticker with only short-option exposure (e.g.
    # UUUU sell-puts) is visible even when equity qty is 0.
    open_option_contracts: Decimal = Decimal("0")
    # Phase 3 density extras — populated only when as_of is provided to the
    # compute function. None when not computed (older callers unaffected).
    days_held: int | None = None  # oldest open lot age, in days
    lt_qty: Decimal = Decimal("0")  # qty held > 365 days
    st_qty: Decimal = Decimal("0")  # qty held <= 365 days
    premium_received: Decimal = Decimal("0")  # net option premium captured on this underlying
    # True iff at least one open lot has a non-zero, non-null cost_basis. False
    # signals "provably missing" (e.g. transferred-in lots without user-set basis)
    # so the renderer can show a "basis missing" chip instead of $0.00.
    basis_known: bool = True
    # Sub-account suffixes (e.g. ["lt", "st"]) and the full display labels for
    # the Account column chip. Single-account rows render the label directly;
    # multi-account rows show a single "lt+st" chip with a tooltip listing
    # every label.
    account_chip: str = ""
    account_displays: tuple[str, ...] = ()


@dataclass(frozen=True)
class OpenOptionRow:
    """One open option position — long or short — for the unified Holdings panel.

    ``cash_basis`` is the unsigned cash flow on the open contracts: for long
    rows the cost paid (BTO debit), for short rows the premium received (STO
    credit minus any BTC). The renderer signs it based on ``side``.
    """

    side: str  # "long" or "short"
    account: str
    ticker: str
    strike: float
    expiry: date
    call_put: str  # "P" or "C"
    qty: Decimal  # positive number of contracts; side flag carries direction
    opened_at: date | None
    cash_basis: Decimal  # long: cost paid; short: premium received (both positive)
    contract_multiplier: int = 100

    @property
    def cash_secured(self) -> Decimal:
        if self.side == "short" and self.call_put == "P":
            return Decimal(str(self.strike)) * self.qty * Decimal(str(self.contract_multiplier))
        return Decimal("0")


@dataclass(frozen=True)
class OpenShortOptionRow:
    """One open short option position (STO not yet covered).

    Surfaced on the ticker drilldown so cash-secured puts and covered calls
    show up alongside long lots. Quantity is reported as a positive number of
    contracts short. ``cash_secured`` is the strike-times-shares the user has
    pledged when this is a put (NaN when not applicable / call)."""

    account: str
    ticker: str
    strike: float
    expiry: date
    call_put: str  # "P" or "C"
    qty_short: Decimal  # positive
    premium_received: Decimal  # net premium kept on this chain
    opened_at: date | None
    contract_multiplier: int = 100

    @property
    def cash_secured(self) -> Decimal:
        if self.call_put != "P":
            return Decimal("0")
        return Decimal(str(self.strike)) * self.qty_short * Decimal(str(self.contract_multiplier))


@dataclass(frozen=True)
class KpiSet:
    period_label: str
    # Tax-recognized realized P&L: matches Schwab UI / Form 8949 — wash-sale
    # disallowed losses are added back to this lot's P&L (they shift to the
    # replacement lot's basis instead).
    period_realized: Decimal
    period_unrealized: Decimal | None
    lifetime_realized: Decimal
    lifetime_unrealized: Decimal | None
    open_position_value: Decimal | None
    lifetime_net_pl: Decimal | None  # realized + unrealized; None when prices unavailable
    missing_symbols: tuple[str, ...] = ()  # tickers without a quote — affected KPIs are partial sums
    today_change: Decimal | None = None  # $ change vs previous close (Today tile)
    today_pct: Decimal | None = None  # % change vs previous close (Today tile)
    # Economic realized P&L: actual cash netted, *excluding* the wash-sale
    # add-back. Equals ``period_realized - disallowed_loss_in_period``. Shown
    # alongside the recognized number on the Realized P/L tile so the user
    # sees both views without switching pages.
    period_realized_economic: Decimal = Decimal("0")
    lifetime_realized_economic: Decimal = Decimal("0")


@dataclass(frozen=True)
class BenchmarkPoint:
    """One point in the benchmark shadow-account series. Same date-axis as
    the AccountValuePoint series; the value is the dollar value of a
    hypothetical 'buy SPY with the same cash flows' account on that date."""

    on: date
    value: Decimal | None  # None when the close on that date is unavailable


@dataclass(frozen=True)
class AccountValuePoint:
    """One point in the account-value time series.

    Anchors the redesigned equity curve. ``contributions`` is the bottom
    baseline (cumulative net deposits). ``account_value`` is the top line
    (cash + marked-to-market holdings). ``net_pl`` is the colored gap
    between them. Any of the priced fields can be None when historical
    closes are missing for one or more held tickers on this date.
    """

    on: date
    contributions: Decimal
    holdings_value: Decimal | None
    cash_balance: Decimal
    account_value: Decimal | None
    net_pl: Decimal | None


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

    rank: int  # 1-based; 0 reserved for "rest" or "cash" aggregate
    symbol: str  # "OTHER" for the rest aggregate, "Cash" for the cash slice
    market_value: Decimal
    pct: Decimal  # 0..100, of total market value (or account value when cash present)
    is_rest: bool
    is_cash: bool = False
    is_pledged_cash: bool = False  # cash currently securing a short put (CSP collateral)


@dataclass(frozen=True)
class AllocationView:
    total_market_value: Decimal
    symbol_count: int
    slices: tuple[AllocationSlice, ...]  # length = top_n + (1 if rest else 0)
    top1_pct: Decimal
    top3_pct: Decimal
    top5_pct: Decimal
    top10_pct: Decimal
    # Every priced holding (no top-N aggregation, no synthetic 'OTHER').
    # Used by the click-through allocation details modal so the user can see
    # the full ranked breakdown including small positions hidden in 'OTHER'.
    all_slices: tuple[AllocationSlice, ...] = ()


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
    net_contributions: Decimal  # lifetime cumulative — used by growth math
    period_net_contributions: Decimal  # period-bounded — matches the provenance modal on the KPI card
    holdings_value: Decimal
    account_value: Decimal
    growth: Decimal
    growth_pct: Decimal | None  # None when starting + period contributions == 0
    cash_share_pct: Decimal
    period_starting_value: Decimal = Decimal("0")  # account value at last second of period start; 0 for Lifetime


@dataclass(frozen=True)
class ClosedLotRow:
    """One historical realized lot for the Closed positions tab.

    Sourced from the Realized G/L CSV (one row per closed buy lot). Realized
    P/L is ``proceeds - cost_basis``; the ``term`` field carries Schwab's
    short/long classification straight through.
    """

    account: str  # account_display, e.g. "Schwab/Brokerage"
    ticker: str
    qty: Decimal
    cost_basis: Decimal
    proceeds: Decimal
    realized_pl: Decimal
    opened_date: date
    closed_date: date
    term: str  # "Short Term" | "Long Term"
    wash_sale: bool
    disallowed_loss: Decimal
    option_strike: float | None = None
    option_expiry: str | None = None  # ISO date string straight from GL CSV
    option_call_put: str | None = None  # "C" or "P"

    @property
    def is_option(self) -> bool:
        return self.option_strike is not None

    @property
    def display_symbol(self) -> str:
        if not self.is_option:
            return self.ticker
        cp = "CALL" if self.option_call_put == "C" else "PUT"
        return f"{self.ticker} {cp} ${self.option_strike:g} {self.option_expiry}"
