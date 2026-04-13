from datetime import date

from tests.conftest import LossSaleFactory, TradeFactory

from net_alpha.engine.detector import detect_wash_sales


def test_simple_equity_wash_sale():
    """Sell TSLA at loss, rebuy within 30 days → Confirmed."""
    sell = LossSaleFactory(
        account="Schwab",
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=10.0,
        proceeds=2400.0,
        cost_basis=3600.0,
    )
    buy = TradeFactory(
        account="Robinhood",
        date=date(2024, 11, 3),
        ticker="TSLA",
        action="Buy",
        quantity=15.0,
        cost_basis=3750.0,
    )
    result = detect_wash_sales([sell, buy], {})

    assert len(result.violations) == 1
    v = result.violations[0]
    assert v.loss_trade_id == sell.id
    assert v.replacement_trade_id == buy.id
    assert v.confidence == "Confirmed"
    assert v.disallowed_loss == 1200.0
    assert v.matched_quantity == 10.0


def test_no_wash_sale_outside_window():
    """Buy 31 days after sell → no wash sale."""
    sell = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=10.0,
        proceeds=2400.0,
        cost_basis=3600.0,
    )
    buy = TradeFactory(
        date=date(2024, 11, 15),  # Day 31
        ticker="TSLA",
        action="Buy",
        quantity=10.0,
    )
    result = detect_wash_sales([sell, buy], {})
    assert len(result.violations) == 0


def test_no_wash_sale_on_gain():
    """Sell at a gain → no wash sale regardless of repurchase."""
    sell = TradeFactory(
        action="Sell",
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=10.0,
        proceeds=5000.0,
        cost_basis=3600.0,
    )
    buy = TradeFactory(
        date=date(2024, 10, 20),
        ticker="TSLA",
        action="Buy",
        quantity=10.0,
    )
    result = detect_wash_sales([sell, buy], {})
    assert len(result.violations) == 0


def test_look_back_window():
    """Buy 15 days BEFORE loss sale → still a wash sale."""
    buy = TradeFactory(
        date=date(2024, 10, 1),
        ticker="TSLA",
        action="Buy",
        quantity=10.0,
        cost_basis=2500.0,
    )
    sell = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=10.0,
        proceeds=2000.0,
        cost_basis=3000.0,
    )
    result = detect_wash_sales([sell, buy], {})
    assert len(result.violations) == 1
    assert result.violations[0].confidence == "Confirmed"
