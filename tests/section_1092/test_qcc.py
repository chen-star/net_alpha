from decimal import Decimal

from net_alpha.section_1092.qcc import is_qualified_covered_call


def test_dte_under_30_days_fails():
    qualifies, reason = is_qualified_covered_call(
        underlying_price_at_write=Decimal("150"),
        strike=Decimal("160"),
        days_to_expiry_at_write=20,
    )
    assert qualifies is False
    assert "30" in reason


def test_dte_over_33_months_fails():
    qualifies, reason = is_qualified_covered_call(
        underlying_price_at_write=Decimal("150"),
        strike=Decimal("160"),
        days_to_expiry_at_write=33 * 30 + 5,
    )
    assert qualifies is False
    assert "33" in reason or "long" in reason.lower()


def test_atm_call_60_days_qualifies():
    qualifies, _ = is_qualified_covered_call(
        underlying_price_at_write=Decimal("100"),
        strike=Decimal("100"),
        days_to_expiry_at_write=60,
    )
    assert qualifies is True


def test_otm_call_60_days_qualifies():
    qualifies, _ = is_qualified_covered_call(
        underlying_price_at_write=Decimal("100"),
        strike=Decimal("110"),
        days_to_expiry_at_write=60,
    )
    assert qualifies is True


def test_itm_call_60_days_fails_short_dated_no_cushion():
    # DTE ≤ 90 days: any ITM strike fails (no LQB cushion).
    qualifies, reason = is_qualified_covered_call(
        underlying_price_at_write=Decimal("100"),
        strike=Decimal("95"),
        days_to_expiry_at_write=60,
    )
    assert qualifies is False
    assert "ITM" in reason or "in-the-money" in reason.lower() or "deep" in reason.lower()


def test_slightly_itm_long_dated_call_qualifies():
    # DTE > 90 days, price > $25, strike at 95% of price — within LQB floor (90%).
    qualifies, _ = is_qualified_covered_call(
        underlying_price_at_write=Decimal("100"),
        strike=Decimal("95"),
        days_to_expiry_at_write=180,
    )
    assert qualifies is True


def test_deep_itm_long_dated_call_fails():
    # DTE > 90 days, strike at 80% of price — below 90% LQB floor.
    qualifies, reason = is_qualified_covered_call(
        underlying_price_at_write=Decimal("100"),
        strike=Decimal("80"),
        days_to_expiry_at_write=180,
    )
    assert qualifies is False
    assert "LQB" in reason or "deep" in reason.lower()


def test_low_priced_stock_atm_required():
    # Stock ≤ $25: no LQB cushion at any DTE — strike must be ≥ ATM.
    qualifies, _ = is_qualified_covered_call(
        underlying_price_at_write=Decimal("20"),
        strike=Decimal("19"),
        days_to_expiry_at_write=180,
    )
    assert qualifies is False


def test_low_priced_stock_atm_qualifies():
    qualifies, _ = is_qualified_covered_call(
        underlying_price_at_write=Decimal("20"),
        strike=Decimal("20"),
        days_to_expiry_at_write=180,
    )
    assert qualifies is True
