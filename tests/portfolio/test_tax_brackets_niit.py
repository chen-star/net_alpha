from decimal import Decimal

from net_alpha.portfolio.tax_planner import TaxBrackets


def test_niit_enabled_defaults_true():
    b = TaxBrackets(
        filing_status="single",
        state="",
        federal_marginal_rate=Decimal("0.37"),
        state_marginal_rate=Decimal("0"),
        ltcg_rate=Decimal("0.20"),
        qualified_div_rate=Decimal("0.20"),
    )
    assert b.niit_enabled is True


def test_niit_enabled_can_be_disabled():
    b = TaxBrackets(
        filing_status="single",
        state="",
        federal_marginal_rate=Decimal("0.37"),
        state_marginal_rate=Decimal("0"),
        ltcg_rate=Decimal("0.20"),
        qualified_div_rate=Decimal("0.20"),
        niit_enabled=False,
    )
    assert b.niit_enabled is False
