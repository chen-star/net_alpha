import datetime as dt
from decimal import Decimal

from net_alpha.portfolio.cash_flow import compute_chart_head_kpis
from net_alpha.portfolio.models import (
    AccountValuePoint,
    CashDeploymentPoint,
)


def _avp(d, contribs, cash, holdings):
    return AccountValuePoint(
        on=d,
        contributions=Decimal(str(contribs)),
        holdings_value=Decimal(str(holdings)) if holdings is not None else None,
        cash_balance=Decimal(str(cash)),
        account_value=((Decimal(str(cash)) + Decimal(str(holdings))) if holdings is not None else None),
        net_pl=None,
    )


def _cdp(d, free, pledged, invested):
    return CashDeploymentPoint(
        on=d,
        free_cash=Decimal(str(free)),
        pledged=Decimal(str(pledged)) if pledged is not None else None,
        invested=Decimal(str(invested)) if invested is not None else None,
    )


def test_empty_series_returns_all_none():
    kpis = compute_chart_head_kpis(
        account_points=[],
        cash_deployment_points=[],
        lifetime_cash_points=[],
        period_starting_value=Decimal("0"),
    )
    assert kpis.end_account_value is None
    assert kpis.end_contributions == Decimal("0")
    assert kpis.period_growth is None
    assert kpis.period_growth_pct is None
    assert kpis.lifetime_min is None and kpis.lifetime_max is None


def test_positive_growth_pct():
    avps = [
        _avp(dt.date(2026, 1, 1), 200_000, 5_000, 195_000),
        _avp(dt.date(2026, 5, 1), 216_200, 28_400, 219_910),
    ]
    cdps = [
        _cdp(dt.date(2026, 1, 1), 5_000, 0, 195_000),
        _cdp(dt.date(2026, 5, 1), 23_400, 5_000, 219_910),
    ]
    kpis = compute_chart_head_kpis(
        account_points=avps,
        cash_deployment_points=cdps,
        lifetime_cash_points=cdps,
        period_starting_value=Decimal("200000"),
    )
    assert kpis.end_account_value == Decimal("248310")
    assert kpis.period_growth == Decimal("32110")
    assert kpis.period_growth_pct is not None
    assert abs(kpis.period_growth_pct - Decimal("0.1485")) < Decimal("0.001")
    assert kpis.end_free_cash == Decimal("23400")
    assert kpis.end_pledged == Decimal("5000")
    assert kpis.end_invested == Decimal("219910")


def test_negative_growth_pct():
    avps = [
        _avp(dt.date(2026, 1, 1), 200_000, 5_000, 195_000),
        _avp(dt.date(2026, 5, 1), 200_000, 5_000, 180_000),
    ]
    cdps = [
        _cdp(dt.date(2026, 1, 1), 5_000, 0, 195_000),
        _cdp(dt.date(2026, 5, 1), 5_000, 0, 180_000),
    ]
    kpis = compute_chart_head_kpis(
        account_points=avps,
        cash_deployment_points=cdps,
        lifetime_cash_points=cdps,
        period_starting_value=Decimal("200000"),
    )
    assert kpis.period_growth == Decimal("-15000")
    assert kpis.period_growth_pct is not None
    assert kpis.period_growth_pct < 0


def test_zero_basis_growth_pct_is_none():
    avps = [_avp(dt.date(2026, 1, 1), 0, 100, 0)]
    cdps = [_cdp(dt.date(2026, 1, 1), 100, 0, 0)]
    kpis = compute_chart_head_kpis(
        account_points=avps,
        cash_deployment_points=cdps,
        lifetime_cash_points=cdps,
        period_starting_value=Decimal("0"),
    )
    assert kpis.period_growth_pct is None


def test_lifetime_min_max_picked_from_lifetime_series():
    lifetime = [
        _cdp(dt.date(2024, 3, 5), 4_200, 0, 0),
        _cdp(dt.date(2024, 7, 1), 25_000, 0, 0),
        _cdp(dt.date(2024, 10, 12), 61_000, 0, 0),
    ]
    period = [_cdp(dt.date(2026, 5, 1), 23_400, 5_000, 219_910)]
    kpis = compute_chart_head_kpis(
        account_points=[_avp(dt.date(2026, 5, 1), 216_200, 28_400, 219_910)],
        cash_deployment_points=period,
        lifetime_cash_points=lifetime,
        period_starting_value=Decimal("216200"),
    )
    assert kpis.lifetime_min == Decimal("4200")
    assert kpis.lifetime_min_on == dt.date(2024, 3, 5)
    assert kpis.lifetime_max == Decimal("61000")
    assert kpis.lifetime_max_on == dt.date(2024, 10, 12)


def test_period_pipeline_first_avp_carries_pre_period_contributions():
    """End-to-end regression for the equity-curve panel-head sign bug.

    Pipeline mirrors web/routes/portfolio.py (post-fix):
      build_cash_balance_series(period=None) → build_account_value_series → compute_chart_head_kpis

    Setup: $50k deposited 2025-06-01 (pre-period), $5k deposited 2026-03-01
    (in-period). Holdings worth $0 (cash only). Eval axis spans the YTD-2026
    window, with the first eval_date (Jan 1) preceding the first in-period
    cash event (Mar 1).

    Bug history: route used to call build_cash_balance_series with period=YTD,
    truncating to in-period points only. build_account_value_series then had
    no cash_point ≤ Jan 1 (the first in-period emission was Mar 1) and AVP[0]
    silently defaulted to contributions=0. compute_chart_head_kpis then
    computed period_contrib = end_contrib − 0 = $55k (lifetime), yielding
    period_growth = 55000 − 50000 − 55000 = −$50k (phantom drawdown rendered
    as ``−$28k (−24.8%)`` next to a chart that was visibly +).

    Fix: route now passes lifetime cash_points; AVP[0].contributions anchors
    on the cumulative-through-period-start total ($50k), so period_contrib
    = $5k and period_growth = 0.
    """
    from net_alpha.models.domain import CashEvent
    from net_alpha.portfolio.account_value import build_account_value_series
    from net_alpha.portfolio.cash_flow import build_cash_balance_series

    events = [
        CashEvent(
            account="Schwab/Tax",
            event_date=dt.date(2025, 6, 1),
            kind="transfer_in",
            amount=50000,
        ),
        CashEvent(
            account="Schwab/Tax",
            event_date=dt.date(2026, 3, 1),
            kind="transfer_in",
            amount=5000,
        ),
    ]
    # POST-FIX: routes must pass lifetime cash_points (period=None). This is
    # the function's documented contract.
    lifetime_cash_points = build_cash_balance_series(
        events=events,
        trades=[],
        period=None,
    )
    eval_dates = [dt.date(2026, 1, 1), dt.date(2026, 3, 1), dt.date(2026, 5, 1)]

    account_points = build_account_value_series(
        trades=[],
        lots=[],
        cash_points=lifetime_cash_points,
        eval_dates=eval_dates,
        get_close=lambda s, d: None,
    )
    # First AVP must anchor on pre-period cumulative contribs ($50k), not 0.
    assert account_points[0].contributions == Decimal("50000")
    assert account_points[0].cash_balance == Decimal("50000")
    # Last AVP carries the full lifetime cumulative.
    assert account_points[-1].contributions == Decimal("55000")
    assert account_points[-1].cash_balance == Decimal("55000")

    cdps = [
        _cdp(dt.date(2026, 1, 1), 50000, 0, 0),
        _cdp(dt.date(2026, 3, 1), 55000, 0, 0),
        _cdp(dt.date(2026, 5, 1), 55000, 0, 0),
    ]
    kpis = compute_chart_head_kpis(
        account_points=account_points,
        cash_deployment_points=cdps,
        lifetime_cash_points=cdps,
        period_starting_value=Decimal("50000"),
    )
    # period_contrib = end ($55k) − first ($50k) = $5k; growth = end_val − start − contrib = 0.
    assert kpis.period_growth == Decimal("0.00")


def test_period_pipeline_buggy_input_documents_regression():
    """Documents the OLD failure mode: passing period-scoped cash_points to
    build_account_value_series silently produces AVP[0].contributions=0 when
    eval_dates predate the first in-period cash event. This test pins the
    misuse so future refactors can't accidentally reintroduce the route bug.

    If the function is ever hardened to accept period-scoped input directly
    (e.g. by emitting a pre-period anchor in build_cash_balance_series),
    DELETE this test rather than weakening it.
    """
    from net_alpha.models.domain import CashEvent
    from net_alpha.portfolio.account_value import build_account_value_series
    from net_alpha.portfolio.cash_flow import build_cash_balance_series

    events = [
        CashEvent(
            account="Schwab/Tax",
            event_date=dt.date(2025, 6, 1),
            kind="transfer_in",
            amount=50000,
        ),
        CashEvent(
            account="Schwab/Tax",
            event_date=dt.date(2026, 3, 1),
            kind="transfer_in",
            amount=5000,
        ),
    ]
    period_cash_points = build_cash_balance_series(
        events=events, trades=[], period=(2026, 2027)
    )
    # Sanity: period filter only affects emission, cumulative still lifetime.
    assert period_cash_points[0].cumulative_contributions == Decimal("55000")

    account_points = build_account_value_series(
        trades=[],
        lots=[],
        cash_points=period_cash_points,
        eval_dates=[dt.date(2026, 1, 1)],
        get_close=lambda s, d: None,
    )
    # Documented failure: no cp ≤ Jan 1 means anchor stays at 0.
    assert account_points[0].contributions == Decimal("0")
