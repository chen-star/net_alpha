import datetime as dt
from datetime import date
from decimal import Decimal

from net_alpha.models.domain import Lot, Trade
from net_alpha.portfolio.account_value import (
    build_account_value_series,
    build_eval_dates,
    holdings_value_at,
)
from net_alpha.portfolio.models import AccountValuePoint, CashBalancePoint


def test_account_value_point_constructs_with_all_fields():
    p = AccountValuePoint(
        on=date(2025, 8, 14),
        contributions=Decimal("200000"),
        holdings_value=Decimal("180000"),
        cash_balance=Decimal("87432"),
        account_value=Decimal("267432"),
        net_pl=Decimal("67432"),
    )
    assert p.on == date(2025, 8, 14)
    assert p.account_value == Decimal("267432")
    assert p.net_pl == Decimal("67432")


def test_account_value_point_allows_none_for_unpriced_dates():
    p = AccountValuePoint(
        on=date(2025, 8, 14),
        contributions=Decimal("200000"),
        holdings_value=None,
        cash_balance=Decimal("87432"),
        account_value=None,
        net_pl=None,
    )
    assert p.holdings_value is None
    assert p.account_value is None
    assert p.net_pl is None


def test_eval_dates_year_period_weekly_plus_today():
    today = date(2025, 8, 14)
    dates = build_eval_dates(period=(2025, 2026), today=today, event_dates=[])
    # First point is Jan 1, last is today; intermediate Fridays (weekly).
    assert dates[0] == date(2025, 1, 3)  # first Friday of 2025 is Jan 3
    assert dates[-1] == today
    # Roughly 32 Fridays Jan→mid-Aug + today
    assert 30 <= len(dates) <= 35
    # Strictly ascending, no duplicates
    assert dates == sorted(set(dates))


def test_eval_dates_event_dates_are_appended_and_deduped():
    today = date(2025, 8, 14)
    events = [date(2025, 3, 12), date(2025, 7, 4), date(2025, 1, 3)]  # last collides w/ Jan 3 Fri
    dates = build_eval_dates(period=(2025, 2026), today=today, event_dates=events)
    assert date(2025, 3, 12) in dates
    assert date(2025, 7, 4) in dates
    assert dates.count(date(2025, 1, 3)) == 1  # deduped
    assert dates == sorted(set(dates))


def test_eval_dates_lifetime_uses_monthly_cadence():
    # Lifetime: period=None; first event date anchors the start.
    today = date(2025, 8, 14)
    events = [date(2022, 5, 10), date(2024, 1, 15), today]
    dates = build_eval_dates(period=None, today=today, event_dates=events)
    # ~ (2025-08 minus 2022-05) months ≈ 39 monthly points + 3 events + today
    assert dates[0] == date(2022, 5, 10)
    assert dates[-1] == today
    # Monthly: at least 30 anchor points, at most ~50
    assert 30 <= len(dates) <= 60


def test_eval_dates_year_in_progress_ends_at_today_not_dec_31():
    today = date(2025, 8, 14)
    dates = build_eval_dates(period=(2025, 2026), today=today, event_dates=[])
    assert max(dates) == today
    assert date(2025, 12, 31) not in dates


def test_eval_dates_completed_year_ends_at_dec_31():
    today = date(2026, 5, 2)
    dates = build_eval_dates(period=(2025, 2026), today=today, event_dates=[])
    assert max(dates) == date(2025, 12, 31)


def _trade(*, ticker: str, action: str, qty: float, basis: float | None, proceeds: float | None, on: dt.date) -> Trade:
    return Trade(
        account="A1",
        date=on,
        ticker=ticker,
        action=action,
        quantity=qty,
        cost_basis=basis,
        proceeds=proceeds,
    )


def _lot(*, ticker: str, qty: float, basis: float, on: dt.date) -> Lot:
    return Lot(
        trade_id="t1",
        account="A1",
        date=on,
        ticker=ticker,
        quantity=qty,
        cost_basis=basis,
        adjusted_basis=basis,
    )


def test_holdings_value_pure_equity_marked_to_market():
    trades = [_trade(ticker="AAPL", action="Buy", qty=10, basis=1500, proceeds=None, on=dt.date(2025, 1, 5))]
    lots = [_lot(ticker="AAPL", qty=10, basis=1500, on=dt.date(2025, 1, 5))]
    closes = {(("AAPL"), dt.date(2025, 6, 1)): Decimal("180")}
    val, missing = holdings_value_at(
        on=dt.date(2025, 6, 1),
        trades=trades,
        lots=lots,
        get_close=lambda sym, d: closes.get((sym, d)),
    )
    assert val == Decimal("1800.00")  # 10 × $180
    assert missing == ()


def test_holdings_value_excludes_lots_acquired_after_D():
    trades = [
        _trade(ticker="AAPL", action="Buy", qty=10, basis=1500, proceeds=None, on=dt.date(2025, 1, 5)),
        _trade(ticker="AAPL", action="Buy", qty=5, basis=900, proceeds=None, on=dt.date(2025, 7, 1)),
    ]
    lots = [
        _lot(ticker="AAPL", qty=10, basis=1500, on=dt.date(2025, 1, 5)),
        _lot(ticker="AAPL", qty=5, basis=900, on=dt.date(2025, 7, 1)),
    ]
    val, _ = holdings_value_at(
        on=dt.date(2025, 6, 1),
        trades=trades,
        lots=lots,
        get_close=lambda sym, d: Decimal("180"),
    )
    assert val == Decimal("1800.00")  # only the Jan-5 lot held on Jun-1


def test_holdings_value_excludes_sold_quantity_as_of_D():
    trades = [
        _trade(ticker="AAPL", action="Buy", qty=10, basis=1500, proceeds=None, on=dt.date(2025, 1, 5)),
        _trade(ticker="AAPL", action="Sell", qty=4, basis=600, proceeds=720, on=dt.date(2025, 4, 1)),
    ]
    lots = [_lot(ticker="AAPL", qty=10, basis=1500, on=dt.date(2025, 1, 5))]
    val, _ = holdings_value_at(
        on=dt.date(2025, 6, 1),
        trades=trades,
        lots=lots,
        get_close=lambda sym, d: Decimal("180"),
    )
    assert val == Decimal("1080.00")  # 6 × $180 (10 bought, 4 sold by Jun-1)


def test_holdings_value_forward_fills_within_7_days():
    trades = [_trade(ticker="AAPL", action="Buy", qty=10, basis=1500, proceeds=None, on=dt.date(2025, 1, 5))]
    lots = [_lot(ticker="AAPL", qty=10, basis=1500, on=dt.date(2025, 1, 5))]
    # Jun 1 missing, Jun 3 (2 days earlier) available
    quotes = {dt.date(2025, 5, 30): Decimal("175")}
    val, missing = holdings_value_at(
        on=dt.date(2025, 6, 1),
        trades=trades,
        lots=lots,
        get_close=lambda sym, d: quotes.get(d),
    )
    assert val == Decimal("1750.00")
    assert missing == ()


def test_holdings_value_returns_none_when_forward_fill_exhausted():
    trades = [_trade(ticker="AAPL", action="Buy", qty=10, basis=1500, proceeds=None, on=dt.date(2025, 1, 5))]
    lots = [_lot(ticker="AAPL", qty=10, basis=1500, on=dt.date(2025, 1, 5))]
    val, missing = holdings_value_at(
        on=dt.date(2025, 6, 1),
        trades=trades,
        lots=lots,
        get_close=lambda sym, d: None,  # no quotes anywhere
    )
    assert val is None
    assert missing == ("AAPL",)


def test_holdings_value_options_carry_at_adjusted_basis():
    from net_alpha.models.domain import OptionDetails

    opt = OptionDetails(strike=200, expiry=dt.date(2025, 12, 19), call_put="C")
    t = Trade(
        account="A1",
        date=dt.date(2025, 3, 1),
        ticker="NVDA",
        action="Buy",
        quantity=2,
        cost_basis=400,
        proceeds=None,
        option_details=opt,
    )
    lot = Lot(
        trade_id="t1",
        account="A1",
        date=dt.date(2025, 3, 1),
        ticker="NVDA",
        quantity=2,
        cost_basis=400,
        adjusted_basis=400,
        option_details=opt,
    )
    val, missing = holdings_value_at(
        on=dt.date(2025, 6, 1),
        trades=[t],
        lots=[lot],
        get_close=lambda sym, d: None,  # never called for options
    )
    assert val == Decimal("400")
    assert missing == ()


def test_holdings_value_empty_portfolio():
    val, missing = holdings_value_at(
        on=dt.date(2025, 6, 1),
        trades=[],
        lots=[],
        get_close=lambda sym, d: Decimal("100"),
    )
    assert val == Decimal("0")
    assert missing == ()


def test_account_value_series_deposit_only_no_trades():
    """$10k deposited Jan 5; no trades. Account value == cash == contributions
    on every date; net P&L is zero throughout."""
    cash_points = [
        CashBalancePoint(
            on=dt.date(2025, 1, 5), cash_balance=Decimal("10000"), cumulative_contributions=Decimal("10000")
        ),
    ]
    series = build_account_value_series(
        trades=[],
        lots=[],
        cash_points=cash_points,
        eval_dates=[dt.date(2025, 1, 5), dt.date(2025, 6, 1)],
        get_close=lambda s, d: Decimal("100"),
    )
    assert len(series) == 2
    for p in series:
        assert p.cash_balance == Decimal("10000")
        assert p.holdings_value == Decimal("0")
        assert p.account_value == Decimal("10000")
        assert p.contributions == Decimal("10000")
        assert p.net_pl == Decimal("0")


def test_account_value_series_buy_then_market_moves():
    """Jan 5: deposit $10k. Jan 10: buy 50 sh AAPL @ $100 = $5k, $5k cash left.
    Jun 1: AAPL @ $130 → holdings $6500, account $11500, P&L +$1500."""
    cash_points = [
        CashBalancePoint(
            on=dt.date(2025, 1, 5), cash_balance=Decimal("10000"), cumulative_contributions=Decimal("10000")
        ),
        CashBalancePoint(
            on=dt.date(2025, 1, 10), cash_balance=Decimal("5000"), cumulative_contributions=Decimal("10000")
        ),
    ]
    trades = [_trade(ticker="AAPL", action="Buy", qty=50, basis=5000, proceeds=None, on=dt.date(2025, 1, 10))]
    lots = [_lot(ticker="AAPL", qty=50, basis=5000, on=dt.date(2025, 1, 10))]
    quotes = {dt.date(2025, 6, 1): Decimal("130"), dt.date(2025, 1, 10): Decimal("100")}

    series = build_account_value_series(
        trades=trades,
        lots=lots,
        cash_points=cash_points,
        eval_dates=[dt.date(2025, 1, 10), dt.date(2025, 6, 1)],
        get_close=lambda s, d: quotes.get(d),
    )
    jun = series[1]
    assert jun.cash_balance == Decimal("5000")
    assert jun.holdings_value == Decimal("6500.00")
    assert jun.account_value == Decimal("11500.00")
    assert jun.contributions == Decimal("10000")
    assert jun.net_pl == Decimal("1500.00")


def test_account_value_series_missing_close_propagates_none():
    cash_points = [
        CashBalancePoint(
            on=dt.date(2025, 1, 5), cash_balance=Decimal("5000"), cumulative_contributions=Decimal("10000")
        ),
    ]
    trades = [_trade(ticker="AAPL", action="Buy", qty=50, basis=5000, proceeds=None, on=dt.date(2025, 1, 5))]
    lots = [_lot(ticker="AAPL", qty=50, basis=5000, on=dt.date(2025, 1, 5))]

    series = build_account_value_series(
        trades=trades,
        lots=lots,
        cash_points=cash_points,
        eval_dates=[dt.date(2025, 6, 1)],
        get_close=lambda s, d: None,  # no prices
    )
    p = series[0]
    assert p.holdings_value is None
    assert p.account_value is None
    assert p.net_pl is None
    assert p.cash_balance == Decimal("5000")
    assert p.contributions == Decimal("10000")


def test_account_value_series_no_cash_points_returns_empty():
    series = build_account_value_series(
        trades=[],
        lots=[],
        cash_points=[],
        eval_dates=[dt.date(2025, 6, 1)],
        get_close=lambda s, d: Decimal("100"),
    )
    assert series == []


def test_account_value_series_cash_balance_steps_with_deposits():
    """Two deposits before the eval date — the latest one wins."""
    cash_points = [
        CashBalancePoint(
            on=dt.date(2025, 1, 5), cash_balance=Decimal("5000"), cumulative_contributions=Decimal("5000")
        ),
        CashBalancePoint(
            on=dt.date(2025, 3, 1), cash_balance=Decimal("8000"), cumulative_contributions=Decimal("8000")
        ),
    ]
    series = build_account_value_series(
        trades=[],
        lots=[],
        cash_points=cash_points,
        eval_dates=[dt.date(2025, 1, 5), dt.date(2025, 2, 15), dt.date(2025, 3, 1)],
        get_close=lambda s, d: Decimal("100"),
    )
    assert series[0].cash_balance == Decimal("5000")
    assert series[1].cash_balance == Decimal("5000")  # walks forward to last <= D
    assert series[2].cash_balance == Decimal("8000")
