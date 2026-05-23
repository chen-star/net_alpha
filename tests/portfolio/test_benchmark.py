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


def test_contribution_on_weekend_forward_fills_to_next_trading_day():
    """Audit #37: cash that arrives on a weekend or holiday must still buy
    benchmark shares — markets are closed so we forward-fill the close to
    the next trading day. Pre-fix the cash was permanently lost from the
    benchmark series because ``get_close(symbol, weekend_date)`` returned
    None and the helper bailed.

    Setup: Saturday 2026-01-03 contribution $1,000 with SPY close None
    on Saturday and Sunday, but $400 on Monday 2026-01-05.
    Expected shares purchased: $1,000 / $400 = 2.5.
    """
    sat = date(2026, 1, 3)
    sun = date(2026, 1, 4)
    mon = date(2026, 1, 5)
    cash_points = [
        CashBalancePoint(on=sat, cash_balance=Decimal("1000"), cumulative_contributions=Decimal("1000")),
    ]
    quotes = {
        sat: None,
        sun: None,
        mon: Decimal("400"),
    }
    series = build_benchmark_series(
        symbol="SPY",
        eq_dates=[mon],
        cash_points=cash_points,
        get_close=lambda s, d: quotes.get(d),
    )
    # 2.5 shares × $400 on Monday = $1,000.
    assert series[-1].value == Decimal("1000.00")


def test_contribution_on_long_weekend_forward_fills_up_to_five_days():
    """Long weekend / Monday holiday: a Friday-evening contribution that
    settles Saturday with the next trading day on Tuesday must still buy
    shares. Forward-fill probes a small window (5 calendar days) so a
    typical 3-day holiday weekend is covered.
    """
    sat = date(2026, 1, 17)  # Saturday, prior to MLK Monday
    tue = date(2026, 1, 20)  # Markets open Tuesday after MLK Monday
    cash_points = [
        CashBalancePoint(on=sat, cash_balance=Decimal("500"), cumulative_contributions=Decimal("500")),
    ]
    quotes = {
        sat: None,
        date(2026, 1, 18): None,  # Sun
        date(2026, 1, 19): None,  # MLK Monday
        tue: Decimal("250"),
    }
    series = build_benchmark_series(
        symbol="SPY",
        eq_dates=[tue],
        cash_points=cash_points,
        get_close=lambda s, d: quotes.get(d),
    )
    # 2 shares × $250 = $500 → cash isn't dropped from the series.
    assert series[-1].value == Decimal("500.00")


def test_contribution_with_no_close_within_window_is_skipped():
    """Defensive: if no trading day appears within the forward-fill window
    (e.g. the user's last quote is from 6+ days before the contribution
    date), the contribution is silently skipped rather than crashing.
    Matches pre-fix behavior for the truly-unrecoverable case.
    """
    cash_points = [
        CashBalancePoint(
            on=date(2026, 1, 1), cash_balance=Decimal("1000"), cumulative_contributions=Decimal("1000")
        ),
    ]
    # No quote anywhere — get_close returns None everywhere.
    series = build_benchmark_series(
        symbol="SPY",
        eq_dates=[date(2026, 1, 1)],
        cash_points=cash_points,
        get_close=lambda s, d: None,
    )
    # No quote for any eval date → BenchmarkPoint(value=None) for the eval
    # date and zero shares purchased.
    assert series == [BenchmarkPoint(on=date(2026, 1, 1), value=None)]
