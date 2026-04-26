import datetime as dt
from decimal import Decimal

from net_alpha.models.domain import Lot, Trade
from net_alpha.portfolio.positions import compute_open_positions
from net_alpha.pricing.provider import Quote


def _trade(**kw):
    defaults = dict(
        id="t1",
        account="Schwab Tax",
        date=dt.date(2025, 1, 15),
        ticker="SPY",
        action="Buy",
        quantity=100.0,
        proceeds=None,
        cost_basis=40_000.0,
        basis_unknown=False,
        option_details=None,
    )
    defaults.update(kw)
    return Trade(**defaults)


def _lot(**kw):
    defaults = dict(
        id="l1",
        trade_id="t1",
        account="Schwab Tax",
        date=dt.date(2025, 1, 15),
        ticker="SPY",
        quantity=100.0,
        cost_basis=40_000.0,
        adjusted_basis=40_000.0,
        option_details=None,
    )
    defaults.update(kw)
    return Lot(**defaults)


def _quote(symbol, price):
    return Quote(symbol=symbol, price=Decimal(str(price)), as_of=dt.datetime.now(dt.UTC), source="yahoo")


def test_single_lot_single_buy_no_sells():
    trades = [_trade()]
    lots = [_lot()]
    rows = compute_open_positions(
        trades=trades, lots=lots, prices={"SPY": _quote("SPY", 460)}, period=None, account=None
    )
    assert len(rows) == 1
    r = rows[0]
    assert r.symbol == "SPY"
    assert r.qty == Decimal("100")
    assert r.market_value == Decimal("46000")
    assert r.open_cost == Decimal("40000")
    assert r.avg_basis == Decimal("400")
    assert r.cash_sunk_per_share == Decimal("400")  # no sells → buys / qty
    assert r.unrealized_pl == Decimal("6000")


def test_position_with_sell_reduces_cash_sunk():
    trades = [
        _trade(id="t1", quantity=100.0, cost_basis=40_000.0),
        _trade(
            id="t2", action="Sell", quantity=50.0, proceeds=25_000.0, cost_basis=20_000.0, date=dt.date(2025, 6, 10)
        ),
    ]
    lots = [_lot(quantity=50.0, cost_basis=20_000.0, adjusted_basis=20_000.0)]
    rows = compute_open_positions(
        trades=trades, lots=lots, prices={"SPY": _quote("SPY", 520)}, period=None, account=None
    )
    r = rows[0]
    assert r.qty == Decimal("50")
    assert r.open_cost == Decimal("20000")
    assert r.cash_sunk_per_share == Decimal("300")  # (40000 − 25000) / 50


def test_missing_price_yields_none_market_value_and_unrealized():
    trades = [_trade()]
    lots = [_lot()]
    rows = compute_open_positions(trades=trades, lots=lots, prices={}, period=None, account=None)
    r = rows[0]
    assert r.market_value is None
    assert r.unrealized_pl is None


def test_account_filter_drops_other_accounts():
    trades = [
        _trade(id="t1", account="Schwab Tax"),
        _trade(id="t2", account="Schwab IRA", quantity=10.0, cost_basis=4_000.0),
    ]
    lots = [
        _lot(id="l1", account="Schwab Tax"),
        _lot(id="l2", account="Schwab IRA", quantity=10.0, cost_basis=4_000.0, adjusted_basis=4_000.0),
    ]
    rows = compute_open_positions(
        trades=trades, lots=lots, prices={"SPY": _quote("SPY", 460)}, period=None, account="Schwab Tax"
    )
    assert len(rows) == 1
    assert rows[0].qty == Decimal("100")


def test_accounts_field_lists_all_holders():
    trades = [
        _trade(id="t1", account="Schwab Tax"),
        _trade(id="t2", account="Schwab IRA", quantity=10.0, cost_basis=4_000.0),
    ]
    lots = [
        _lot(id="l1", account="Schwab Tax"),
        _lot(id="l2", account="Schwab IRA", quantity=10.0, cost_basis=4_000.0, adjusted_basis=4_000.0),
    ]
    rows = compute_open_positions(
        trades=trades, lots=lots, prices={"SPY": _quote("SPY", 460)}, period=None, account=None
    )
    r = rows[0]
    assert set(r.accounts) == {"Schwab Tax", "Schwab IRA"}


def test_period_filter_scopes_realized_pl():
    trades = [
        _trade(id="t1", quantity=100.0, cost_basis=40_000.0),  # buy 2025-01-15
        _trade(
            id="t2", action="Sell", quantity=30.0, proceeds=15_000.0, cost_basis=12_000.0, date=dt.date(2025, 6, 10)
        ),  # +3000 in 2025
        _trade(
            id="t3", action="Sell", quantity=20.0, proceeds=10_000.0, cost_basis=8_000.0, date=dt.date(2026, 3, 1)
        ),  # +2000 in 2026
    ]
    lots = [_lot(quantity=50.0, cost_basis=20_000.0, adjusted_basis=20_000.0)]
    # YTD 2026 only: should see only the +2000 sell
    rows = compute_open_positions(
        trades=trades,
        lots=lots,
        prices={"SPY": _quote("SPY", 460)},
        period=(2026, 2027),
        account=None,
    )
    assert rows[0].realized_pl == Decimal("2000")
    # Lifetime: should see both sells = +5000
    rows = compute_open_positions(
        trades=trades,
        lots=lots,
        prices={"SPY": _quote("SPY", 460)},
        period=None,
        account=None,
    )
    assert rows[0].realized_pl == Decimal("5000")


def test_option_lots_excluded_from_qty_and_basis():
    from net_alpha.models.domain import OptionDetails

    option_details = OptionDetails(strike=500.0, expiry=dt.date(2026, 6, 20), call_put="C")
    lots = [
        _lot(id="l1"),  # equity SPY
        _lot(id="l2", quantity=1.0, cost_basis=500.0, adjusted_basis=500.0, option_details=option_details),
    ]
    rows = compute_open_positions(
        trades=[_trade()],
        lots=lots,
        prices={"SPY": _quote("SPY", 460)},
        period=None,
        account=None,
    )
    # Only the equity lot contributes to qty
    assert rows[0].qty == Decimal("100")
    assert rows[0].open_cost == Decimal("40000")
