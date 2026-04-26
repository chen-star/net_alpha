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
        _buy(dt.date(2026, 3, 5)),                              # buys ignored
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
        _sell(dt.date(2026, 4, 2), proceeds=800, cost=1200),   # -400
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
        Trade(account="Tax", date=dt.date(2026, 7, 2), ticker="SPY", action="Sell",
              quantity=10.0, proceeds=None, cost_basis=1000.0),
        Trade(account="Tax", date=dt.date(2026, 7, 3), ticker="SPY", action="Sell",
              quantity=10.0, proceeds=1500.0, cost_basis=None),
    ]
    out = monthly_realized_pl(trades=trades, year=2026, ticker=None, account=None)
    jul = next(m for m in out if m.month == 7)
    assert jul.trade_count == 1
    assert jul.net_pl == Decimal("500")
