import datetime as dt

from net_alpha.portfolio.month_end_equity import (
    month_end_equity_series,
)


def _const_close(_ticker, _on):
    return None


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
