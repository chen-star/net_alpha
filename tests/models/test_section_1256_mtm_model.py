from datetime import date
from decimal import Decimal

from net_alpha.models.domain import Section1256MTM


def test_round_trip_basic():
    m = Section1256MTM(
        position_key="SPX|4000.0|2026-06-19|C|fidelity",
        tax_year=2025,
        last_business_day=date(2025, 12, 31),
        fmv=Decimal("125.50"),
        basis_before=Decimal("100.00"),
        unrealized_pnl=Decimal("25.50"),
        long_term_portion=Decimal("15.30"),
        short_term_portion=Decimal("10.20"),
        fmv_source="yahoo_close",
        ticker="SPX",
    )
    dumped = m.model_dump_json()
    restored = Section1256MTM.model_validate_json(dumped)
    assert restored == m


def test_lt_st_sums_to_unrealized():
    m = Section1256MTM(
        position_key="SPX|4000.0|2026-06-19|C|fidelity",
        tax_year=2025,
        last_business_day=date(2025, 12, 31),
        fmv=Decimal("125.50"),
        basis_before=Decimal("100.00"),
        unrealized_pnl=Decimal("25.50"),
        long_term_portion=Decimal("15.30"),
        short_term_portion=Decimal("10.20"),
        fmv_source="yahoo_close",
        ticker="SPX",
    )
    assert m.long_term_portion + m.short_term_portion == m.unrealized_pnl
