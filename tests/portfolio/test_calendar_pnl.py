import datetime as dt
from decimal import Decimal

from net_alpha.models.domain import Trade
from net_alpha.portfolio.calendar_pnl import monthly_realized_pl


def _sell(day, *, ticker="SPY", account="Tax", proceeds, cost, qty=10.0):
    return Trade(
        account=account,
        date=day,
        ticker=ticker,
        action="Sell",
        quantity=qty,
        proceeds=proceeds,
        cost_basis=cost,
    )


def _buy(day, *, ticker="SPY", account="Tax", cost=1000.0, qty=10.0):
    return Trade(
        account=account,
        date=day,
        ticker=ticker,
        action="Buy",
        quantity=qty,
        proceeds=None,
        cost_basis=cost,
    )


def test_returns_12_months_for_year_with_no_trades():
    out = monthly_realized_pl(trades=[], year=2026, ticker=None, account=None)
    assert len(out) == 12
    assert all(m.net_pl == Decimal("0") for m in out)
    assert all(m.trade_count == 0 for m in out)
    assert [m.month for m in out] == list(range(1, 13))


def test_aggregates_only_sells_in_target_year():
    trades = [
        _sell(dt.date(2026, 3, 5), proceeds=1500, cost=1000),  # gain 500 in Mar
        _sell(dt.date(2025, 3, 5), proceeds=1500, cost=1000),  # different year — skipped
        _buy(dt.date(2026, 3, 5)),  # buys ignored
    ]
    out = monthly_realized_pl(trades=trades, year=2026, ticker=None, account=None)
    march = next(m for m in out if m.month == 3)
    assert march.net_pl == Decimal("500")
    assert march.gross_gain == Decimal("500")
    assert march.gross_loss == Decimal("0")
    assert march.trade_count == 1
    feb = next(m for m in out if m.month == 2)
    assert feb.net_pl == Decimal("0")
    assert feb.trade_count == 0


def test_mixed_month_splits_gain_and_loss():
    trades = [
        _sell(dt.date(2026, 4, 1), proceeds=1500, cost=1000),  # +500
        _sell(dt.date(2026, 4, 2), proceeds=800, cost=1200),  # -400
    ]
    out = monthly_realized_pl(trades=trades, year=2026, ticker=None, account=None)
    apr = next(m for m in out if m.month == 4)
    assert apr.net_pl == Decimal("100")
    assert apr.gross_gain == Decimal("500")
    assert apr.gross_loss == Decimal("400")
    assert apr.trade_count == 2


def test_ticker_filter_drops_other_tickers():
    trades = [
        _sell(dt.date(2026, 5, 10), ticker="SPY", proceeds=1500, cost=1000),
        _sell(dt.date(2026, 5, 11), ticker="QQQ", proceeds=2000, cost=1000),
    ]
    out = monthly_realized_pl(trades=trades, year=2026, ticker="SPY", account=None)
    may = next(m for m in out if m.month == 5)
    assert may.net_pl == Decimal("500")
    assert may.trade_count == 1


def test_account_filter_drops_other_accounts():
    trades = [
        _sell(dt.date(2026, 6, 10), account="schwab/tax", proceeds=1500, cost=1000),
        _sell(dt.date(2026, 6, 11), account="schwab/ira", proceeds=2000, cost=1000),
    ]
    out = monthly_realized_pl(trades=trades, year=2026, ticker=None, account="schwab/tax")
    jun = next(m for m in out if m.month == 6)
    assert jun.net_pl == Decimal("500")
    assert jun.trade_count == 1


def test_trades_with_missing_proceeds_or_cost_skipped():
    trades = [
        _sell(dt.date(2026, 7, 1), proceeds=1500, cost=1000),
        Trade(
            account="Tax",
            date=dt.date(2026, 7, 2),
            ticker="SPY",
            action="Sell",
            quantity=10.0,
            proceeds=None,
            cost_basis=1000.0,
        ),
        Trade(
            account="Tax",
            date=dt.date(2026, 7, 3),
            ticker="SPY",
            action="Sell",
            quantity=10.0,
            proceeds=1500.0,
            cost_basis=None,
        ),
    ]
    out = monthly_realized_pl(trades=trades, year=2026, ticker=None, account=None)
    jul = next(m for m in out if m.month == 7)
    assert jul.trade_count == 1
    assert jul.net_pl == Decimal("500")


def test_year_boundary_dec31_jan1():
    trades = [
        _sell(dt.date(2026, 12, 31), proceeds=1500, cost=1000),  # last day — included
        _sell(dt.date(2027, 1, 1), proceeds=1500, cost=1000),  # next year — excluded
    ]
    out = monthly_realized_pl(trades=trades, year=2026, ticker=None, account=None)
    dec = next(m for m in out if m.month == 12)
    assert dec.trade_count == 1
    assert dec.net_pl == Decimal("500")


# ---------------------------------------------------------------------------
# Tests for monthly_realized_pl_series — the chronological-series wrapper
# used by the Portfolio overview's wide bar chart. Honors the page Period
# selector (YTD / specific year / Lifetime) by truncating future months and
# spanning multiple years for Lifetime.
# ---------------------------------------------------------------------------

from net_alpha.portfolio.calendar_pnl import monthly_realized_pl_series  # noqa: E402
from net_alpha.portfolio.models import MonthlyPnlPoint  # noqa: E402


def test_series_ytd_truncates_future_months():
    """YTD scope: emit Jan..today.month only — no future months."""
    today = dt.date(2026, 5, 3)
    trades = [
        _sell(dt.date(2026, 3, 5), proceeds=1500, cost=1000),  # +500 in Mar
    ]
    out = monthly_realized_pl_series(
        trades=trades,
        period=(2026, 2027),
        account=None,
        today=today,
    )
    # YTD on May 3rd, 2026 -> Jan(1) Feb(2) Mar(3) Apr(4) May(5) = 5 entries.
    assert len(out) == 5
    assert all(p.year == 2026 for p in out)
    assert [p.month for p in out] == [1, 2, 3, 4, 5]
    mar = next(p for p in out if p.month == 3)
    assert mar.net_pl == Decimal("500")
    assert mar.trade_count == 1


def test_series_specific_year_returns_full_12_months():
    """A historical year scope returns all 12 months even if today is mid-year."""
    today = dt.date(2026, 5, 3)
    trades = [
        _sell(dt.date(2025, 11, 4), proceeds=1500, cost=1000),  # +500
    ]
    out = monthly_realized_pl_series(
        trades=trades,
        period=(2025, 2026),
        account=None,
        today=today,
    )
    assert len(out) == 12
    assert all(p.year == 2025 for p in out)
    assert [p.month for p in out] == list(range(1, 13))
    nov = next(p for p in out if p.month == 11)
    assert nov.net_pl == Decimal("500")
    other_months = [p for p in out if p.month != 11]
    assert all(p.net_pl == Decimal("0") and p.trade_count == 0 for p in other_months)


def test_series_lifetime_spans_first_trade_year_through_today():
    """Lifetime: first trade year (Jan) through today.year (today.month)."""
    today = dt.date(2026, 5, 3)
    trades = [
        _sell(dt.date(2024, 9, 1), proceeds=2000, cost=1000),  # +1000 in Sep '24
        _sell(dt.date(2026, 3, 5), proceeds=1500, cost=1000),  # +500 in Mar '26
    ]
    out = monthly_realized_pl_series(
        trades=trades,
        period=None,  # Lifetime
        account=None,
        today=today,
    )
    # 2024: Jan..Dec = 12, 2025: Jan..Dec = 12, 2026: Jan..May = 5 -> 29 total.
    assert len(out) == 29
    assert out[0].year == 2024 and out[0].month == 1
    assert out[-1].year == 2026 and out[-1].month == 5
    # Months are strictly chronological.
    seen = [(p.year, p.month) for p in out]
    assert seen == sorted(seen)
    # Activity months populated correctly.
    sep24 = next(p for p in out if p.year == 2024 and p.month == 9)
    mar26 = next(p for p in out if p.year == 2026 and p.month == 3)
    assert sep24.net_pl == Decimal("1000")
    assert mar26.net_pl == Decimal("500")
    # Inter-year gap (all of 2025) is filled with zero entries.
    y2025 = [p for p in out if p.year == 2025]
    assert len(y2025) == 12
    assert all(p.net_pl == Decimal("0") and p.trade_count == 0 for p in y2025)


def test_series_lifetime_with_no_trades_returns_empty():
    """Lifetime with no trades at all — return empty list (no axis to draw)."""
    today = dt.date(2026, 5, 3)
    out = monthly_realized_pl_series(
        trades=[],
        period=None,
        account=None,
        today=today,
    )
    assert out == []


def test_series_account_filter_propagates():
    """The account filter is forwarded to the underlying per-year function."""
    today = dt.date(2026, 5, 3)
    trades = [
        _sell(dt.date(2026, 2, 10), account="schwab/tax", proceeds=1500, cost=1000),
        _sell(dt.date(2026, 2, 11), account="schwab/ira", proceeds=2000, cost=1000),
    ]
    out = monthly_realized_pl_series(
        trades=trades,
        period=(2026, 2027),
        account="schwab/tax",
        today=today,
    )
    feb = next(p for p in out if p.month == 2)
    assert feb.net_pl == Decimal("500")
    assert feb.trade_count == 1


def test_series_returns_monthly_pnl_point_instances():
    """Sanity: rows are MonthlyPnlPoint dataclasses with the expected shape."""
    today = dt.date(2026, 5, 3)
    out = monthly_realized_pl_series(
        trades=[],
        period=(2026, 2027),
        account=None,
        today=today,
    )
    assert len(out) == 5
    for p in out:
        assert isinstance(p, MonthlyPnlPoint)
        assert p.year == 2026
        assert p.net_pl == Decimal("0")
