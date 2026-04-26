import datetime as dt
from decimal import Decimal

from net_alpha.models.domain import Lot, Trade
from net_alpha.portfolio.pnl import compute_kpis
from net_alpha.pricing.provider import Quote


def _trade(**kw):
    defaults = dict(
        id="t1",
        account="Tax",
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
        account="Tax",
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


def test_kpis_zero_when_no_trades():
    k = compute_kpis(trades=[], lots=[], prices={}, period_label="YTD", period=(2026, 2027), account=None)
    assert k.period_realized == Decimal("0")
    assert k.lifetime_realized == Decimal("0")
    assert k.open_position_value == Decimal("0")


def test_kpis_realized_split_by_period():
    trades = [
        _trade(id="t1", action="Sell", date=dt.date(2025, 6, 10), quantity=10, proceeds=5_000, cost_basis=4_000),
        _trade(id="t2", action="Sell", date=dt.date(2026, 3, 1), quantity=10, proceeds=6_000, cost_basis=4_500),
    ]
    k = compute_kpis(trades=trades, lots=[], prices={}, period_label="YTD", period=(2026, 2027), account=None)
    assert k.period_realized == Decimal("1500")
    assert k.lifetime_realized == Decimal("2500")


def test_kpis_unrealized_uses_prices_when_available():
    lots = [_lot()]
    k = compute_kpis(
        trades=[_trade()],
        lots=lots,
        prices={"SPY": _quote("SPY", 460)},
        period_label="YTD",
        period=(2026, 2027),
        account=None,
    )
    assert k.open_position_value == Decimal("46000")
    assert k.period_unrealized == Decimal("6000")
    assert k.lifetime_unrealized == Decimal("6000")


def test_kpis_unrealized_none_when_prices_missing():
    lots = [_lot()]
    k = compute_kpis(trades=[_trade()], lots=lots, prices={}, period_label="YTD", period=(2026, 2027), account=None)
    assert k.open_position_value is None
    assert k.period_unrealized is None
    assert k.lifetime_unrealized is None
