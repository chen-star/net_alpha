from datetime import date

from net_alpha.models.realized_gl import RealizedGLLot


def test_realized_gl_lot_required_fields():
    lot = RealizedGLLot(
        account_display="schwab/personal",
        symbol_raw="WRD",
        ticker="WRD",
        closed_date=date(2026, 4, 20),
        opened_date=date(2026, 2, 11),
        quantity=100.0,
        proceeds=824.96,
        cost_basis=800.66,
        unadjusted_cost_basis=800.66,
        wash_sale=False,
        disallowed_loss=0.0,
        term="Short Term",
    )
    assert lot.ticker == "WRD"
    assert lot.wash_sale is False
    assert lot.option_strike is None


def test_realized_gl_lot_with_option_fields():
    lot = RealizedGLLot(
        account_display="schwab/personal",
        symbol_raw="CRCL 06/18/2026 150.00 C",
        ticker="CRCL",
        closed_date=date(2026, 4, 20),
        opened_date=date(2026, 4, 17),
        quantity=1.0,
        proceeds=330.33,
        cost_basis=460.66,
        unadjusted_cost_basis=460.66,
        wash_sale=False,
        disallowed_loss=0.0,
        term="Short Term",
        option_strike=150.00,
        option_expiry="2026-06-18",
        option_call_put="C",
    )
    assert lot.option_strike == 150.00


def test_realized_gl_lot_natural_key_is_deterministic():
    """Two lots with identical invariant fields produce the same natural key."""
    base = dict(
        account_display="schwab/personal",
        symbol_raw="WRD",
        ticker="WRD",
        closed_date=date(2026, 4, 20),
        opened_date=date(2026, 2, 11),
        quantity=100.0,
        proceeds=824.96,
        cost_basis=800.66,
        unadjusted_cost_basis=800.66,
        wash_sale=False,
        disallowed_loss=0.0,
        term="Short Term",
    )
    a = RealizedGLLot(**base)
    b = RealizedGLLot(**base)
    assert a.compute_natural_key() == b.compute_natural_key()


def test_realized_gl_lot_natural_key_changes_with_basis():
    base = dict(
        account_display="schwab/personal",
        symbol_raw="WRD",
        ticker="WRD",
        closed_date=date(2026, 4, 20),
        opened_date=date(2026, 2, 11),
        quantity=100.0,
        proceeds=824.96,
        cost_basis=800.66,
        unadjusted_cost_basis=800.66,
        wash_sale=False,
        disallowed_loss=0.0,
        term="Short Term",
    )
    a = RealizedGLLot(**base)
    b = RealizedGLLot(**{**base, "cost_basis": 750.00})
    assert a.compute_natural_key() != b.compute_natural_key()
