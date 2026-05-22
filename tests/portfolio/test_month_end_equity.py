import datetime as dt
from decimal import Decimal

from net_alpha.portfolio.models import CashBalancePoint
from net_alpha.portfolio.month_end_equity import (
    month_end_equity_series,
)


def _const_close(_ticker, _on):
    return None


def _cp(d: dt.date, cash: str, contrib: str = "0") -> CashBalancePoint:
    return CashBalancePoint(
        on=d,
        cash_balance=Decimal(cash),
        cumulative_contributions=Decimal(contrib),
    )


def test_empty_year_returns_12_future_tiles_with_month_labels():
    tiles = month_end_equity_series(
        year=2026,
        today=dt.date(2026, 5, 22),
        trades=[],
        lots=[],
        cash_points=[],
        get_close=_const_close,
        monthly_realized=[],
    )
    assert len(tiles) == 12
    assert [t.month for t in tiles] == list(range(1, 13))
    assert [t.label for t in tiles] == [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    assert all(t.end_value is None for t in tiles)
    assert all(t.mom_delta_pct is None for t in tiles)
    assert [t.is_future for t in tiles] == [False] * 5 + [True] * 7
    assert all(not t.is_current for t in tiles)


def test_end_value_computed_for_each_completed_month():
    cash_points = [_cp(dt.date(2025, 12, 31), "10000")]
    tiles = month_end_equity_series(
        year=2026,
        today=dt.date(2026, 5, 22),
        trades=[],
        lots=[],
        cash_points=cash_points,
        get_close=_const_close,
        monthly_realized=[],
    )
    for m in range(1, 6):
        assert tiles[m - 1].end_value == Decimal("10000")
    for m in range(6, 13):
        assert tiles[m - 1].end_value is None


def test_current_month_uses_today_not_month_end():
    cash_points = [
        _cp(dt.date(2025, 12, 31), "10000"),
        _cp(dt.date(2026, 5, 10), "12000"),
    ]
    tiles = month_end_equity_series(
        year=2026,
        today=dt.date(2026, 5, 22),
        trades=[],
        lots=[],
        cash_points=cash_points,
        get_close=_const_close,
        monthly_realized=[],
    )
    may = tiles[4]
    assert may.end_value == Decimal("12000")
    assert may.is_current is True
    assert may.is_future is False


def test_historical_year_marks_no_tile_current():
    cash_points = [_cp(dt.date(2024, 12, 31), "10000")]
    tiles = month_end_equity_series(
        year=2025,
        today=dt.date(2026, 5, 22),
        trades=[],
        lots=[],
        cash_points=cash_points,
        get_close=_const_close,
        monthly_realized=[],
    )
    assert all(not t.is_current for t in tiles)
    assert all(not t.is_future for t in tiles)
    assert all(t.end_value == Decimal("10000") for t in tiles)


def test_year_before_any_cash_history_is_all_empty():
    cash_points = [_cp(dt.date(2026, 1, 1), "10000")]
    tiles = month_end_equity_series(
        year=2024,
        today=dt.date(2026, 5, 22),
        trades=[],
        lots=[],
        cash_points=cash_points,
        get_close=_const_close,
        monthly_realized=[],
    )
    assert all(t.end_value is None for t in tiles)
    assert all(not t.is_future for t in tiles)
