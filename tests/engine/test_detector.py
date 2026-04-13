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


def test_fifo_allocation_earliest_buy_first():
    """Multiple buys in window — earliest buy absorbs disallowed loss first."""
    sell = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=10.0,
        proceeds=2000.0,
        cost_basis=3000.0,
    )
    buy1 = TradeFactory(
        date=date(2024, 10, 20),
        ticker="TSLA",
        action="Buy",
        quantity=5.0,
        cost_basis=1200.0,
    )
    buy2 = TradeFactory(
        date=date(2024, 10, 25),
        ticker="TSLA",
        action="Buy",
        quantity=8.0,
        cost_basis=2000.0,
    )
    result = detect_wash_sales([sell, buy1, buy2], {})

    assert len(result.violations) == 2
    # First violation: 5 shares allocated to buy1 (earlier)
    v1 = result.violations[0]
    assert v1.replacement_trade_id == buy1.id
    assert v1.matched_quantity == 5.0
    assert v1.disallowed_loss == 500.0  # 5/10 * 1000

    # Second violation: 5 shares allocated to buy2 (later)
    v2 = result.violations[1]
    assert v2.replacement_trade_id == buy2.id
    assert v2.matched_quantity == 5.0
    assert v2.disallowed_loss == 500.0


def test_partial_wash_sale_fewer_shares_bought():
    """Bought fewer shares than sold — partial wash sale."""
    sell = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=100.0,
        proceeds=20000.0,
        cost_basis=30000.0,
    )
    buy = TradeFactory(
        date=date(2024, 10, 20),
        ticker="TSLA",
        action="Buy",
        quantity=40.0,
        cost_basis=9000.0,
    )
    result = detect_wash_sales([sell, buy], {})

    assert len(result.violations) == 1
    v = result.violations[0]
    assert v.matched_quantity == 40.0
    assert v.disallowed_loss == 4000.0  # 40/100 * 10000


def test_adjusted_basis_updated():
    """Disallowed loss rolls into replacement lot's adjusted basis."""
    sell = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=10.0,
        proceeds=2000.0,
        cost_basis=3200.0,
    )
    buy = TradeFactory(
        date=date(2024, 10, 20),
        ticker="TSLA",
        action="Buy",
        quantity=10.0,
        cost_basis=2500.0,
    )
    result = detect_wash_sales([sell, buy], {})

    # Find the lot for the buy
    lot = next(l for l in result.lots if l.trade_id == buy.id)
    assert lot.cost_basis == 2500.0
    assert lot.adjusted_basis == 2500.0 + 1200.0  # 3700.0


def test_same_day_buy_and_sell():
    """Same-day buy and sell — always a wash sale."""
    sell = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=10.0,
        proceeds=2000.0,
        cost_basis=3000.0,
    )
    buy = TradeFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        action="Buy",
        quantity=10.0,
        cost_basis=2100.0,
    )
    result = detect_wash_sales([sell, buy], {})
    assert len(result.violations) == 1
    assert result.violations[0].confidence == "Confirmed"
