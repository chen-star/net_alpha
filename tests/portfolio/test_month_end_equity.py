import datetime as dt
from decimal import Decimal

from net_alpha.portfolio.models import CashBalancePoint, MonthlyPnl
from net_alpha.portfolio.month_end_equity import (
    month_end_equity_series,
    month_end_equity_summary,
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


def _monthly_pnl_row(month: int, net: str) -> MonthlyPnl:
    return MonthlyPnl(
        month=month,
        net_pl=Decimal(net),
        gross_gain=Decimal("0") if Decimal(net) < 0 else Decimal(net),
        gross_loss=Decimal("0") if Decimal(net) >= 0 else -Decimal(net),
        trade_count=1 if Decimal(net) != 0 else 0,
    )


def test_mom_delta_pct_computed_when_prior_month_present():
    cash_points = [
        _cp(dt.date(2025, 12, 31), "10000"),
        _cp(dt.date(2026, 1, 31), "11000"),
        _cp(dt.date(2026, 2, 28), "10450"),
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
    assert tiles[0].mom_delta_pct == Decimal("10.00")
    assert tiles[1].mom_delta_pct == Decimal("-5.00")


def test_mom_delta_pct_null_when_prior_missing():
    cash_points = [_cp(dt.date(2026, 3, 31), "10000")]
    tiles = month_end_equity_series(
        year=2026,
        today=dt.date(2026, 5, 22),
        trades=[],
        lots=[],
        cash_points=cash_points,
        get_close=_const_close,
        monthly_realized=[],
    )
    assert tiles[0].end_value is None and tiles[0].mom_delta_pct is None
    assert tiles[1].end_value is None and tiles[1].mom_delta_pct is None
    assert tiles[2].end_value == Decimal("10000")
    assert tiles[2].mom_delta_pct is None


def test_cash_delta_tracks_cash_balance_change():
    cash_points = [
        _cp(dt.date(2025, 12, 31), "10000"),
        _cp(dt.date(2026, 1, 31), "12000"),
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
    assert tiles[0].cash_delta == Decimal("2000")


def test_realized_pl_sourced_from_monthly_realized():
    cash_points = [_cp(dt.date(2025, 12, 31), "10000")]
    monthly = [_monthly_pnl_row(m, "0") for m in range(1, 13)]
    monthly[3] = _monthly_pnl_row(4, "1500")
    tiles = month_end_equity_series(
        year=2026,
        today=dt.date(2026, 5, 22),
        trades=[],
        lots=[],
        cash_points=cash_points,
        get_close=_const_close,
        monthly_realized=monthly,
    )
    assert tiles[3].realized_pl == Decimal("1500")
    assert tiles[0].realized_pl == Decimal("0")


def test_summary_returns_none_for_empty_year():
    tiles = month_end_equity_series(
        year=2026,
        today=dt.date(2026, 5, 22),
        trades=[],
        lots=[],
        cash_points=[],
        get_close=_const_close,
        monthly_realized=[],
    )
    assert month_end_equity_summary(tiles, today=dt.date(2026, 5, 22), prior_year_end_value=None) is None


def test_summary_ytd_delta_uses_prior_year_end_anchor():
    cash_points = [
        _cp(dt.date(2025, 12, 31), "100000"),
        _cp(dt.date(2026, 1, 31), "102000"),
        _cp(dt.date(2026, 2, 28), "101000"),
        _cp(dt.date(2026, 3, 31), "104000"),
        _cp(dt.date(2026, 4, 30), "108000"),
        _cp(dt.date(2026, 5, 22), "107000"),
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
    summary = month_end_equity_summary(
        tiles,
        today=dt.date(2026, 5, 22),
        prior_year_end_value=Decimal("100000"),
    )
    assert summary is not None
    assert summary["ytd_delta_abs"] == Decimal("8000.00")
    assert summary["ytd_delta_pct"] == Decimal("8.00")
    assert summary["best_month_label"] == "Apr"
    assert summary["worst_month_label"] == "Feb"


def test_summary_omits_ytd_when_anchor_unknown():
    cash_points = [
        _cp(dt.date(2025, 12, 31), "100000"),
        _cp(dt.date(2026, 1, 31), "102000"),
    ]
    tiles = month_end_equity_series(
        year=2026,
        today=dt.date(2026, 2, 15),
        trades=[],
        lots=[],
        cash_points=cash_points,
        get_close=_const_close,
        monthly_realized=[],
    )
    summary = month_end_equity_summary(tiles, today=dt.date(2026, 2, 15), prior_year_end_value=None)
    assert summary is not None
    assert summary["ytd_delta_abs"] is None
    assert summary["ytd_delta_pct"] is None
    assert summary["best_month_label"] == "Jan"
    assert summary["worst_month_label"] == "Jan"


def test_summary_with_zero_anchor_returns_pct_none_not_divzero():
    cash_points = [
        _cp(dt.date(2025, 12, 31), "0"),
        _cp(dt.date(2026, 1, 31), "5000"),
    ]
    tiles = month_end_equity_series(
        year=2026,
        today=dt.date(2026, 2, 15),
        trades=[],
        lots=[],
        cash_points=cash_points,
        get_close=_const_close,
        monthly_realized=[],
    )
    summary = month_end_equity_summary(tiles, today=dt.date(2026, 2, 15), prior_year_end_value=Decimal("0"))
    assert summary is not None
    assert summary["ytd_delta_abs"] == Decimal("5000.00")
    assert summary["ytd_delta_pct"] is None
