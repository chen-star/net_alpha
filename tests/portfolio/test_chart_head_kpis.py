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
