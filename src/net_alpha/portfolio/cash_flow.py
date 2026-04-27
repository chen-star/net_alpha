"""Pure functions for cash-balance, contributions, and cash-share computations.

No DB access; takes lists of events/trades, returns models. Mirrors the
shape of `equity_curve.py` (sort by date, fold over events, emit one point
per event date).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from decimal import Decimal

from net_alpha.models.domain import CashEvent, Trade
from net_alpha.portfolio.models import CashBalancePoint, CashFlowKPIs


# Sign rules — positive amount means cash inflow.
_INFLOW_KINDS = {"transfer_in", "dividend", "interest", "sweep_in"}
_OUTFLOW_KINDS = {"transfer_out", "fee", "sweep_out"}
_CONTRIB_INFLOW = {"transfer_in"}
_CONTRIB_OUTFLOW = {"transfer_out"}


def _trade_cash_delta(t: Trade) -> Decimal:
    """Signed cash impact of a trade. Positive = cash in, negative = cash out."""
    if t.gross_cash_impact is not None:
        return Decimal(str(t.gross_cash_impact))
    # Legacy fallback for trades imported before gross_cash_impact existed.
    if t.action == "Sell" and t.proceeds is not None:
        return Decimal(str(t.proceeds))
    if t.action == "Buy" and t.cost_basis is not None:
        return Decimal(str(-t.cost_basis))
    return Decimal("0")


def _event_cash_delta(e: CashEvent) -> Decimal:
    if e.kind in _INFLOW_KINDS:
        return Decimal(str(e.amount))
    if e.kind in _OUTFLOW_KINDS:
        return Decimal(str(-e.amount))
    return Decimal("0")


def _event_contrib_delta(e: CashEvent) -> Decimal:
    if e.kind in _CONTRIB_INFLOW:
        return Decimal(str(e.amount))
    if e.kind in _CONTRIB_OUTFLOW:
        return Decimal(str(-e.amount))
    return Decimal("0")


def build_cash_balance_series(
    *,
    events: Iterable[CashEvent],
    trades: Iterable[Trade],
    account: str | None,
    period: tuple[int, int] | None,
) -> list[CashBalancePoint]:
    """Return one point per distinct event date, with running cash balance.

    `account=None` includes all accounts. `period=None` includes everything.
    `period=(y, y+1)` restricts the *displayed* points to year `y`; events
    before `y` still contribute to the opening balance carried into year `y`.
    """
    # Filter by account first.
    events_list = [e for e in events if account is None or e.account == account]
    trades_list = [t for t in trades if account is None or t.account == account]

    # Build (date, balance_delta, contrib_delta) tuples.
    rows: list[tuple[dt.date, Decimal, Decimal]] = []
    for e in events_list:
        rows.append((e.event_date, _event_cash_delta(e), _event_contrib_delta(e)))
    for t in trades_list:
        rows.append((t.date, _trade_cash_delta(t), Decimal("0")))

    if not rows:
        return []

    rows.sort(key=lambda r: r[0])

    # Fold into a running series, accumulating opening balance/contrib for items
    # before the period window.
    pts: list[CashBalancePoint] = []
    bal = Decimal("0")
    contrib = Decimal("0")
    last_emitted_date: dt.date | None = None

    period_start = dt.date(period[0], 1, 1) if period else None
    period_end_excl = dt.date(period[1], 1, 1) if period else None  # exclusive

    for d, bdelta, cdelta in rows:
        bal += bdelta
        contrib += cdelta
        # If outside the period, just keep accumulating opening balance.
        if period_start is not None and d < period_start:
            continue
        if period_end_excl is not None and d >= period_end_excl:
            continue
        if last_emitted_date is None or d != last_emitted_date:
            pts.append(CashBalancePoint(on=d, cash_balance=bal, cumulative_contributions=contrib))
            last_emitted_date = d
        else:
            # Same-day events — fold into the last point.
            pts[-1] = CashBalancePoint(on=d, cash_balance=bal, cumulative_contributions=contrib)
    return pts


def compute_cash_kpis(
    *,
    events: Iterable[CashEvent],
    trades: Iterable[Trade],
    holdings_value: Decimal,
    account: str | None,
    period: tuple[int, int] | None,
) -> CashFlowKPIs:
    """Single-shot summary used by the KPI strip."""
    series = build_cash_balance_series(
        events=events, trades=trades, account=account, period=period,
    )
    if series:
        cash = series[-1].cash_balance
        contrib = series[-1].cumulative_contributions
    else:
        cash = Decimal("0")
        contrib = Decimal("0")

    account_value = cash + holdings_value
    growth = account_value - contrib
    growth_pct: Decimal | None = (growth / contrib) if contrib != 0 else None
    cash_share_pct = (cash / account_value) if account_value != 0 else Decimal("0")
    return CashFlowKPIs(
        cash_balance=cash,
        net_contributions=contrib,
        holdings_value=holdings_value,
        account_value=account_value,
        growth=growth,
        growth_pct=growth_pct,
        cash_share_pct=cash_share_pct,
    )
