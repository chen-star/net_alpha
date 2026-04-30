from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from net_alpha.portfolio.benchmark import build_benchmark_series
from net_alpha.portfolio.models import BenchmarkPoint, CashBalancePoint


def _quote(price: str):
    return Decimal(price)


def test_single_starting_balance_no_contributions():
    """Account seeded Jan-1 at $1000, SPY close $100; on Mar-1 SPY is $110.
    Shadow value Mar-1: 10 sh × $110 = $1100."""
    cash_points = [
        CashBalancePoint(on=date(2025, 1, 1), cash_balance=Decimal("1000"), cumulative_contributions=Decimal("1000")),
    ]
    eq_dates = [date(2025, 1, 1), date(2025, 3, 1)]
    quotes = {
        date(2025, 1, 1): Decimal("100"),
        date(2025, 3, 1): Decimal("110"),
    }
    closes = MagicMock(side_effect=lambda sym, on: quotes.get(on))

    series = build_benchmark_series(
        symbol="SPY",
        eq_dates=eq_dates,
        cash_points=cash_points,
        get_close=closes,
    )
    assert series == [
        BenchmarkPoint(on=date(2025, 1, 1), value=Decimal("1000")),
        BenchmarkPoint(on=date(2025, 3, 1), value=Decimal("1100.00")),
    ]


def test_mid_period_contribution_buys_more_shares():
    """Jan-1 $1000 @ $100 → 10 sh. Feb-1 +$500 contribution @ $125 → 4 more sh
    (14 total). Mar-1 SPY $130 → 14 × 130 = $1820."""
    cash_points = [
        CashBalancePoint(on=date(2025, 1, 1), cash_balance=Decimal("1000"), cumulative_contributions=Decimal("1000")),
        CashBalancePoint(on=date(2025, 2, 1), cash_balance=Decimal("1500"), cumulative_contributions=Decimal("1500")),
    ]
    quotes = {
        date(2025, 1, 1): Decimal("100"),
        date(2025, 2, 1): Decimal("125"),
        date(2025, 3, 1): Decimal("130"),
    }
    series = build_benchmark_series(
        symbol="SPY",
        eq_dates=[date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1)],
        cash_points=cash_points,
        get_close=lambda s, d: quotes.get(d),
    )
    # Mar 1 value = 14 sh × 130 = 1820
    assert series[-1].value == Decimal("1820.00")


def test_missing_close_yields_none_point_without_breaking_chain():
    cash_points = [
        CashBalancePoint(on=date(2025, 1, 1), cash_balance=Decimal("100"), cumulative_contributions=Decimal("100")),
    ]
    quotes = {date(2025, 1, 1): Decimal("100")}  # mid-period close missing
    series = build_benchmark_series(
        symbol="SPY",
        eq_dates=[date(2025, 1, 1), date(2025, 2, 1)],
        cash_points=cash_points,
        get_close=lambda s, d: quotes.get(d),
    )
    assert series[0].value == Decimal("100")
    assert series[1].value is None  # missing close → None, not a crash


def test_no_contributions_returns_empty_list():
    series = build_benchmark_series(
        symbol="SPY",
        eq_dates=[date(2025, 1, 1)],
        cash_points=[],
        get_close=lambda s, d: Decimal("100"),
    )
    assert series == []
