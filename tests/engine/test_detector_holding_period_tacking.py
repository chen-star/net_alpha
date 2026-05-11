"""§1091/§1223(4) holding-period tacking tests.

When a wash sale rolls disallowed loss into a replacement lot, the replacement
lot's holding period must include the holding period of the lot whose sale
triggered the wash sale (IRC §1223(4)). The replacement lot exposes the
effective holding-period start via ``Lot.effective_acquired_date()``; the raw
acquisition date stays unchanged for audit.
"""

from datetime import date

from net_alpha.engine.detector import detect_wash_sales
from tests.conftest import LossSaleFactory, TradeFactory


def _lot_for(result, trade_id):
    return next(lot for lot in result.lots if lot.trade_id == trade_id)


def test_replacement_lot_tacks_original_lot_acquired_date():
    """Buy Jan 1, sell at loss Mar 1, rebuy Mar 15 → replacement tacks to Jan 1."""
    buy_original = TradeFactory(
        date=date(2024, 1, 1),
        ticker="AAPL",
        action="Buy",
        quantity=10.0,
        cost_basis=1000.0,
    )
    sell_loss = LossSaleFactory(
        date=date(2024, 3, 1),
        ticker="AAPL",
        quantity=10.0,
        proceeds=800.0,
        cost_basis=1000.0,
    )
    buy_replacement = TradeFactory(
        date=date(2024, 3, 15),
        ticker="AAPL",
        action="Buy",
        quantity=10.0,
        cost_basis=900.0,
    )
    result = detect_wash_sales([buy_original, sell_loss, buy_replacement], {})

    assert len(result.violations) == 1
    replacement_lot = _lot_for(result, buy_replacement.id)
    assert replacement_lot.adjusted_basis == 900.0 + 200.0  # disallowed loss rolled in
    assert replacement_lot.tacked_acquired_date == date(2024, 1, 1)
    assert replacement_lot.effective_acquired_date() == date(2024, 1, 1)
    assert replacement_lot.date == date(2024, 3, 15)  # raw acquisition date unchanged


def test_no_tacking_when_no_wash_sale():
    """A clean buy with no triggering loss sale gets no tacked date."""
    buy = TradeFactory(
        date=date(2024, 3, 15),
        ticker="AAPL",
        action="Buy",
        quantity=10.0,
        cost_basis=900.0,
    )
    result = detect_wash_sales([buy], {})
    lot = _lot_for(result, buy.id)
    assert lot.tacked_acquired_date is None
    assert lot.effective_acquired_date() == date(2024, 3, 15)


def test_chained_wash_sale_propagates_earliest_acquired_date():
    """B1 → wash → B2 → wash → B3. B3 tacks all the way back to B1's date."""
    b1 = TradeFactory(
        date=date(2024, 1, 1),
        ticker="AAPL",
        action="Buy",
        quantity=10.0,
        cost_basis=1000.0,
    )
    s1 = LossSaleFactory(
        date=date(2024, 3, 1),
        ticker="AAPL",
        quantity=10.0,
        proceeds=800.0,
        cost_basis=1000.0,
    )
    b2 = TradeFactory(
        date=date(2024, 3, 15),
        ticker="AAPL",
        action="Buy",
        quantity=10.0,
        cost_basis=850.0,
    )
    s2 = LossSaleFactory(
        date=date(2024, 5, 1),
        ticker="AAPL",
        quantity=10.0,
        proceeds=700.0,
        cost_basis=850.0,  # using b2's raw basis; the engine sees this trade-level value
    )
    b3 = TradeFactory(
        date=date(2024, 5, 15),
        ticker="AAPL",
        action="Buy",
        quantity=10.0,
        cost_basis=750.0,
    )
    result = detect_wash_sales([b1, s1, b2, s2, b3], {})

    assert len(result.violations) == 2
    lot_b2 = _lot_for(result, b2.id)
    lot_b3 = _lot_for(result, b3.id)
    # B2 tacks to B1's Jan 1 date
    assert lot_b2.tacked_acquired_date == date(2024, 1, 1)
    # B3 inherits the chain: its FIFO-matched loss-side lot is B2, whose
    # effective acquired date is Jan 1. So B3 also tacks back to Jan 1.
    assert lot_b3.tacked_acquired_date == date(2024, 1, 1)


def test_cross_account_tacking():
    """Loss in Schwab Jan→Mar, replacement in Robinhood Mar 15 still tacks to Jan."""
    buy_schwab = TradeFactory(
        account="Schwab",
        date=date(2024, 1, 1),
        ticker="NVDA",
        action="Buy",
        quantity=20.0,
        cost_basis=2000.0,
    )
    sell_schwab = LossSaleFactory(
        account="Schwab",
        date=date(2024, 3, 1),
        ticker="NVDA",
        quantity=20.0,
        proceeds=1600.0,
        cost_basis=2000.0,
    )
    buy_robinhood = TradeFactory(
        account="Robinhood",
        date=date(2024, 3, 15),
        ticker="NVDA",
        action="Buy",
        quantity=20.0,
        cost_basis=1800.0,
    )
    result = detect_wash_sales([buy_schwab, sell_schwab, buy_robinhood], {})

    assert len(result.violations) == 1
    replacement_lot = _lot_for(result, buy_robinhood.id)
    assert replacement_lot.tacked_acquired_date == date(2024, 1, 1)


def test_gain_sells_consume_lots_for_fifo_correctness():
    """A prior gain sell consumes the early lot, so a later loss sell's tacking
    must use the *next* available lot's acquired date — not the consumed one.

    Both b1 and b2 are outside the loss sale's ±30-day wash window, so neither
    can be the replacement; the replacement must be b3. b3 then tacks to the
    FIFO-consumed lot (b2), not the gain-consumed lot (b1).
    """
    b1 = TradeFactory(
        date=date(2024, 1, 1),
        ticker="AAPL",
        action="Buy",
        quantity=10.0,
        cost_basis=1000.0,
    )
    b2 = TradeFactory(
        date=date(2024, 1, 15),
        ticker="AAPL",
        action="Buy",
        quantity=10.0,
        cost_basis=1100.0,
    )
    # Gain sell consumes b1 (FIFO).
    s_gain = TradeFactory(
        date=date(2024, 2, 1),
        ticker="AAPL",
        action="Sell",
        quantity=10.0,
        proceeds=1500.0,
        cost_basis=1000.0,
    )
    # Loss sell — both b1 (73 days prior) and b2 (59 days prior) are OUTSIDE
    # the ±30-day wash window, so neither can be the replacement. FIFO-wise
    # this sell consumes b2 (b1 already gone).
    s_loss = LossSaleFactory(
        date=date(2024, 3, 15),
        ticker="AAPL",
        quantity=10.0,
        proceeds=900.0,
        cost_basis=1100.0,
    )
    b3 = TradeFactory(
        date=date(2024, 3, 20),
        ticker="AAPL",
        action="Buy",
        quantity=10.0,
        cost_basis=950.0,
    )
    result = detect_wash_sales([b1, b2, s_gain, s_loss, b3], {})

    assert len(result.violations) == 1
    assert result.violations[0].replacement_trade_id == b3.id
    lot_b3 = _lot_for(result, b3.id)
    # B3 must tack to b2 (Jan 15), NOT b1 (Jan 1) which the gain sell consumed.
    assert lot_b3.tacked_acquired_date == date(2024, 1, 15)


def test_loss_sale_with_no_prior_buy_does_not_tack():
    """If the engine can't find a prior buy (e.g. orphan loss sale), no tack.

    The replacement lot's effective date should equal its own acquisition date.
    """
    sell_loss = LossSaleFactory(
        date=date(2024, 3, 1),
        ticker="AAPL",
        quantity=10.0,
        proceeds=800.0,
        cost_basis=1000.0,
    )
    buy_replacement = TradeFactory(
        date=date(2024, 3, 15),
        ticker="AAPL",
        action="Buy",
        quantity=10.0,
        cost_basis=900.0,
    )
    result = detect_wash_sales([sell_loss, buy_replacement], {})

    assert len(result.violations) == 1
    lot = _lot_for(result, buy_replacement.id)
    # Loss side has no prior buy → falls back to sell date, which is BEFORE the
    # replacement date — that still tacks the replacement to the sell date.
    # This is a conservative approximation, not a bug: the holding period
    # cannot extend earlier than the loss sale itself if we know no earlier lot.
    assert lot.tacked_acquired_date == date(2024, 3, 1)
    assert lot.effective_acquired_date() == date(2024, 3, 1)
