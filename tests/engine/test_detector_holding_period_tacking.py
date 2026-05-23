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
    """Buy Jan 1, sell at loss Mar 1, rebuy Mar 15 → replacement tacks
    additively per §1223(4): replacement.effective shifts back by the loss
    leg's holding period (Mar 1 − Jan 1 = 60d) → Mar 15 − 60d = Jan 15.
    """
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
    # §1223(4): Mar 15 − 60d loss-leg HP (Mar 1 − Jan 1) = Jan 15
    assert replacement_lot.tacked_acquired_date == date(2024, 1, 15)
    assert replacement_lot.effective_acquired_date() == date(2024, 1, 15)
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
    """B1 → wash → B2 → wash → B3. Under additive §1223(4), each link in the
    chain shifts the next replacement back by the prior loss-leg's HP. The
    loss leg HP itself includes any prior tacking, so the chain compounds.
    """
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
    # §1223(4): Mar 15 − 60d loss-leg HP (Mar 1 − Jan 1) = Jan 15
    assert lot_b2.tacked_acquired_date == date(2024, 1, 15)
    # §1223(4) chained: when s2 (May 1) closes B2 at a loss, B2's effective
    # acquired date is already Jan 15 (tacked above), so the loss-leg HP is
    # May 1 − Jan 15 = 107d. B3 (May 15) − 107d = Jan 29. The compounded
    # back-shift correctly reflects that B2 itself carried the full B1 holding
    # period under §1223(4).
    assert lot_b3.tacked_acquired_date == date(2024, 1, 29)


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
    # §1223(4): Mar 15 − 60d loss-leg HP (Mar 1 − Jan 1) = Jan 15
    assert replacement_lot.tacked_acquired_date == date(2024, 1, 15)


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
    # B3 must tack from b2 (Jan 15), NOT b1 (Jan 1) which the gain sell
    # consumed. §1223(4): Mar 20 − 60d loss-leg HP (Mar 15 − Jan 15) = Jan 20.
    assert lot_b3.tacked_acquired_date == date(2024, 1, 20)


def test_loss_sale_with_no_prior_buy_does_not_tack():
    """Orphan loss sell (no prior buy) → no tacking under additive §1223(4).

    With ``loss_side_acquired`` falling back to ``sell.date``, the loss-leg
    holding period evaluates to 0 days. The ``loss_leg_hp_days > 0`` guard then
    skips tacking entirely — there is no donor holding period to include — and
    the replacement lot's effective date equals its raw acquisition date.
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
    # §1223(4): orphan sell → 0-day loss-leg HP → no tacking applied.
    assert lot.tacked_acquired_date is None
    assert lot.effective_acquired_date() == date(2024, 3, 15)


def test_additive_tacking_diverges_from_earliest_wins_in_rebuy_gap():
    """Replacement bought BEFORE the loss sale, with the loss-leg lot sitting
    outside the ±30-day wash window — additive §1223(4) shifts the replacement's
    effective date back by the loss-leg's full holding period, even though the
    loss-side acquired date itself is *later* than the additive result.

    Setup: buy_loss_leg Feb 10 (outside ±30d window of loss), rebuy
    (replacement) Mar 25, sell at loss Apr 1.
    Loss-leg HP = Apr 1 − Feb 10 = 51d. Replacement Mar 25 − 51d = Feb 3.

    Under the prior earliest-wins semantic this case would have collapsed to
    Feb 10 (the loss-side acquired date — taken as ``min(loss_side, current)``)
    — under-crediting the Feb 10 → Mar 25 rebuy gap. The additive fix credits
    the full 51d holding period, landing at Feb 3.
    """
    buy_loss_leg = TradeFactory(
        date=date(2024, 2, 10),
        ticker="AAPL",
        action="Buy",
        quantity=10.0,
        cost_basis=1000.0,
    )
    # Replacement is acquired BEFORE the loss sale — inside the ±30-day window
    # relative to the eventual loss on Apr 1.
    buy_replacement = TradeFactory(
        date=date(2024, 3, 25),
        ticker="AAPL",
        action="Buy",
        quantity=10.0,
        cost_basis=950.0,
    )
    sell_loss = LossSaleFactory(
        date=date(2024, 4, 1),
        ticker="AAPL",
        quantity=10.0,
        proceeds=800.0,
        cost_basis=1000.0,
    )
    result = detect_wash_sales([buy_loss_leg, buy_replacement, sell_loss], {})

    assert len(result.violations) == 1
    # The wash sale must roll into buy_replacement, not buy_loss_leg
    # (buy_loss_leg is 51d before the loss sale, outside the ±30d window).
    assert result.violations[0].replacement_trade_id == buy_replacement.id
    replacement_lot = _lot_for(result, buy_replacement.id)
    # §1223(4): Mar 25 − 51d loss-leg HP (Apr 1 − Feb 10) = Feb 3
    assert replacement_lot.tacked_acquired_date == date(2024, 2, 3)
    assert replacement_lot.effective_acquired_date() == date(2024, 2, 3)
