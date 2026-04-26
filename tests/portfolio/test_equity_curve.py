import datetime as dt
from decimal import Decimal

from net_alpha.models.domain import Trade
from net_alpha.portfolio.equity_curve import build_equity_curve


def _sell(d, gain):
    return Trade(
        id="t", account="Tax", date=d, ticker="SPY", action="Sell",
        quantity=10.0, proceeds=10_000 + gain, cost_basis=10_000.0,
        basis_unknown=False, option_details=None,
    )


def test_empty_year_yields_zero_baseline_only():
    pts = build_equity_curve(trades=[], year=2026, present_unrealized=None)
    assert len(pts) == 1
    assert pts[0].cumulative_realized == Decimal("0")


def test_cumulative_realized_sorted_by_date():
    trades = [_sell(dt.date(2026, 3, 10), 500), _sell(dt.date(2026, 1, 5), 200)]
    pts = build_equity_curve(trades=trades, year=2026, present_unrealized=None)
    assert pts[0].cumulative_realized == Decimal("0")
    assert pts[1].cumulative_realized == Decimal("200")
    assert pts[2].cumulative_realized == Decimal("700")


def test_trades_outside_year_excluded():
    trades = [_sell(dt.date(2025, 12, 31), 1_000), _sell(dt.date(2026, 2, 1), 250)]
    pts = build_equity_curve(trades=trades, year=2026, present_unrealized=None)
    finals = [p.cumulative_realized for p in pts]
    assert finals[-1] == Decimal("250")


def test_present_day_point_carries_unrealized():
    trades = [_sell(dt.date(2026, 1, 5), 200)]
    pts = build_equity_curve(trades=trades, year=2026, present_unrealized=Decimal("400"))
    last = pts[-1]
    assert last.unrealized == Decimal("400")
    assert last.cumulative_realized == Decimal("200")
