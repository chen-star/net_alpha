"""Pure functions for cash-balance, contributions, and cash-share computations.

No DB access; takes lists of events/trades, returns models. Sorts inputs by
date, folds over events, emits one point per event date.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Sequence
from decimal import Decimal

from net_alpha.models.domain import CashEvent, Trade
from net_alpha.portfolio.models import (
    AccountValuePoint,
    CashBalancePoint,
    CashDeploymentPoint,
    CashFlowKPIs,
    ChartHeadKPIs,
)
from net_alpha.portfolio.positions import compute_open_short_option_positions

# Sign rules — positive amount means cash inflow.
#
# `sweep_in` / `sweep_out` are intentionally absent: those events move money
# between Schwab1 brokerage cash and the Schwab Futures sub-account, but both
# sub-accounts are part of the same Schwab account total. Treating them as
# real cash flows would make our combined cash balance drift from Schwab's
# combined account value as cash sloshes between the two buckets. They are
# cash-neutral here; the per-sub-account split is not surfaced.
_INFLOW_KINDS = {"transfer_in", "dividend", "interest"}
_OUTFLOW_KINDS = {"transfer_out", "fee"}
CONTRIB_INFLOW_KINDS = {"transfer_in"}
CONTRIB_OUTFLOW_KINDS = {"transfer_out"}


def _trade_cash_delta(t: Trade) -> Decimal:
    """Signed cash impact of a trade. Positive = cash in, negative = cash out.

    Share-quantity-only transfers (Schwab Security Transfer / Journaled Shares)
    move shares, not Schwab1 cash, so they contribute zero. The legacy fallback
    below would otherwise fabricate a cash debit/credit from cost_basis/proceeds.
    """
    if t.basis_source in ("transfer_in", "transfer_out"):
        return Decimal("0")
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
    if e.kind in CONTRIB_INFLOW_KINDS:
        return Decimal(str(e.amount))
    if e.kind in CONTRIB_OUTFLOW_KINDS:
        return Decimal(str(-e.amount))
    return Decimal("0")


def build_cash_balance_series(
    *,
    events: Iterable[CashEvent],
    trades: Iterable[Trade],
    accounts: Sequence[str] | None = None,
    period: tuple[int, int] | None,
) -> list[CashBalancePoint]:
    """Return one point per distinct event date, with running cash balance.

    `accounts=None` includes all accounts. `period=None` includes everything.
    `period=(y, y+1)` restricts the *displayed* points to year `y`; events
    before `y` still contribute to the opening balance carried into year `y`.
    """
    _filter = set(accounts) if accounts else None
    # Filter by account first.
    events_list = [e for e in events if _filter is None or e.account in _filter]
    trades_list = [t for t in trades if _filter is None or t.account in _filter]

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
    accounts: Sequence[str] | None = None,
    period: tuple[int, int] | None,
    period_starting_value: Decimal = Decimal("0"),
) -> CashFlowKPIs:
    """Single-shot summary used by the KPI strip."""
    _filter = set(accounts) if accounts else None
    series = build_cash_balance_series(
        events=events,
        trades=trades,
        accounts=accounts,
        period=period,
    )
    if series:
        cash = series[-1].cash_balance
        contrib = series[-1].cumulative_contributions
    else:
        cash = Decimal("0")
        contrib = Decimal("0")

    # Period-bounded contributions: only transfer events whose date falls inside
    # the active period window. Matches the provenance modal so the KPI card
    # reads the same number the user sees when they drill in.
    if period is None:
        period_contrib = contrib
    else:
        period_start = dt.date(period[0], 1, 1)
        period_end_excl = dt.date(period[1], 1, 1)
        period_contrib = Decimal("0")
        for e in events:
            if _filter is not None and e.account not in _filter:
                continue
            if not (period_start <= e.event_date < period_end_excl):
                continue
            period_contrib += _event_contrib_delta(e)

    account_value = cash + holdings_value
    growth = account_value - period_starting_value - period_contrib
    growth_denom = period_starting_value + period_contrib
    growth_pct: Decimal | None = (growth / growth_denom) if growth_denom != 0 else None
    cash_share_pct = (cash / account_value) if account_value != 0 else Decimal("0")
    return CashFlowKPIs(
        cash_balance=cash,
        net_contributions=contrib,
        period_net_contributions=period_contrib,
        holdings_value=holdings_value,
        account_value=account_value,
        growth=growth,
        growth_pct=growth_pct,
        cash_share_pct=cash_share_pct,
        period_starting_value=period_starting_value,
    )


def cash_allocation_slice(
    *,
    events: Iterable[CashEvent],
    trades: Iterable[Trade],
    accounts: Sequence[str] | None = None,
) -> Decimal:
    """Return the current cash balance (lifetime, no period clip).

    Used by the allocation donut to render cash as one extra slice.
    """
    series = build_cash_balance_series(
        events=events,
        trades=trades,
        accounts=accounts,
        period=None,
    )
    return series[-1].cash_balance if series else Decimal("0")


def cash_balance_extremes(
    points: Sequence[CashBalancePoint],
) -> tuple[Decimal, dt.date, Decimal, dt.date] | None:
    """Return (min_balance, min_date, max_balance, max_date) over a cash series.

    Ties: the earliest date wins for both min and max. Returns ``None`` when the
    input is empty. Used by the Overview cash-curve panel to render dashed
    lifetime reference lines while the chart itself stays period-scoped.
    """
    if not points:
        return None
    mn_p = min(points, key=lambda p: (p.cash_balance, p.on))
    mx_p = max(points, key=lambda p: (p.cash_balance, -p.on.toordinal()))
    return mn_p.cash_balance, mn_p.on, mx_p.cash_balance, mx_p.on


def pledged_cash_at(
    *,
    on: dt.date,
    trades: Iterable[Trade],
    accounts: Sequence[str] | None = None,
) -> Decimal:
    """Sum of cash collateral pledged to open short-put positions as of close of ``on``.

    Collateral = strike × 100 × qty_short for each open short put. Only short
    puts pledge cash (CSP collateral); short calls are excluded — they are
    covered-call positions whose "collateral" is the underlying shares, not
    cash. Trades dated after ``on`` are ignored so the function is safe to
    call per-date for a historical series.
    """
    _filter = set(accounts) if accounts else None
    trades_asof = [
        t for t in trades
        if t.date <= on and (_filter is None or t.account in _filter)
    ]
    rows = compute_open_short_option_positions(trades_asof)
    total = Decimal("0")
    for r in rows:
        if r.call_put != "P":
            continue
        total += Decimal(str(r.strike)) * Decimal("100") * r.qty_short
    return total.quantize(Decimal("0.01"))


def build_cash_deployment_series(
    *,
    account_points: Sequence[AccountValuePoint],
    trades: Iterable[Trade],
    events: Iterable[CashEvent],  # noqa: ARG001 - reserved for future use; signature stability
    accounts: Sequence[str] | None,
    with_pledged: bool,
) -> list[CashDeploymentPoint]:
    """Return one CashDeploymentPoint per AccountValuePoint date.

    Reuses the AccountValuePoint series so the deployment chart shares the
    exact same date axis as the equity chart. ``free_cash = cash_balance -
    pledged`` (clamped non-negative); ``pledged`` is the cash collateral on
    open short puts as of that date (or ``None`` when ``with_pledged=False``,
    the fallback path). ``invested`` mirrors ``AccountValuePoint.holdings_value``.

    ``trades`` is the same trade list passed to the equity chart pipeline;
    we filter it per-date via ``pledged_cash_at``.
    """
    trades_list = list(trades)
    pts: list[CashDeploymentPoint] = []
    for avp in account_points:
        cash = avp.cash_balance
        if with_pledged:
            pledged = pledged_cash_at(on=avp.on, trades=trades_list, accounts=accounts)
            if pledged > cash:
                pledged = cash  # clamp — never report more pledged than total
            free = cash - pledged
        else:
            pledged = None
            free = cash
        pts.append(
            CashDeploymentPoint(
                on=avp.on,
                free_cash=free.quantize(Decimal("0.01")),
                pledged=pledged.quantize(Decimal("0.01")) if pledged is not None else None,
                invested=avp.holdings_value,
            )
        )
    return pts


def compute_chart_head_kpis(
    *,
    account_points: Sequence[AccountValuePoint],
    cash_deployment_points: Sequence[CashDeploymentPoint],
    lifetime_cash_points: Sequence[CashDeploymentPoint],
    period_starting_value: Decimal,
) -> ChartHeadKPIs:
    """Inline panel-head numbers for the equity + cash deployment charts.

    Pure-derived from the same series the chart plots. ``lifetime_cash_points``
    is the unscoped (period=None) cash deployment series — used to source the
    lifetime min/max KPI line that replaces the in-chart annotation lines.
    """
    if not account_points:
        return ChartHeadKPIs(
            end_account_value=None,
            end_contributions=Decimal("0"),
            period_growth=None,
            period_growth_pct=None,
            end_free_cash=Decimal("0"),
            end_pledged=Decimal("0"),
            end_invested=None,
            end_cash_share_pct=None,
            lifetime_min=None,
            lifetime_min_on=None,
            lifetime_max=None,
            lifetime_max_on=None,
        )

    last = account_points[-1]
    end_account_value = last.account_value
    end_contributions = last.contributions

    period_contrib = end_contributions - account_points[0].contributions
    growth_denom = period_starting_value + period_contrib
    if end_account_value is None:
        period_growth: Decimal | None = None
        period_growth_pct: Decimal | None = None
    else:
        period_growth = (end_account_value - period_starting_value - period_contrib).quantize(
            Decimal("0.01")
        )
        period_growth_pct = (
            (period_growth / growth_denom) if growth_denom != 0 else None
        )

    if cash_deployment_points:
        last_cdp = cash_deployment_points[-1]
        end_free = last_cdp.free_cash
        end_pledged = last_cdp.pledged if last_cdp.pledged is not None else Decimal("0")
        end_invested = last_cdp.invested
    else:
        end_free = Decimal("0")
        end_pledged = Decimal("0")
        end_invested = None

    if end_account_value and end_account_value > 0:
        end_cash_share_pct = ((end_free + end_pledged) / end_account_value).quantize(
            Decimal("0.0001")
        )
    else:
        end_cash_share_pct = None

    if lifetime_cash_points:
        def _cash(p: CashDeploymentPoint) -> Decimal:
            return p.free_cash + (p.pledged if p.pledged is not None else Decimal("0"))

        mn = min(lifetime_cash_points, key=lambda p: (_cash(p), p.on))
        mx = max(lifetime_cash_points, key=lambda p: (_cash(p), -p.on.toordinal()))
        lifetime_min = _cash(mn)
        lifetime_min_on = mn.on
        lifetime_max = _cash(mx)
        lifetime_max_on = mx.on
    else:
        lifetime_min = lifetime_min_on = lifetime_max = lifetime_max_on = None

    return ChartHeadKPIs(
        end_account_value=end_account_value,
        end_contributions=end_contributions,
        period_growth=period_growth,
        period_growth_pct=period_growth_pct,
        end_free_cash=end_free,
        end_pledged=end_pledged,
        end_invested=end_invested,
        end_cash_share_pct=end_cash_share_pct,
        lifetime_min=lifetime_min,
        lifetime_min_on=lifetime_min_on,
        lifetime_max=lifetime_max,
        lifetime_max_on=lifetime_max_on,
    )
