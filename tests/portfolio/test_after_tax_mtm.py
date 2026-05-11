from decimal import Decimal
from unittest.mock import MagicMock

from net_alpha.portfolio.after_tax import Period, compute_after_tax
from net_alpha.portfolio.tax_planner import TaxBrackets


def _brackets():
    return TaxBrackets(
        filing_status="single",
        state="",
        federal_marginal_rate=Decimal("0.32"),
        ltcg_rate=Decimal("0.15"),
        qualified_div_rate=Decimal("0.15"),
        state_marginal_rate=Decimal("0.0"),
        niit_enabled=False,
    )


def _repo(*, st=0, lt=0, sec1256_realized=0, sec1256_mtm=0, disallowed=0):
    repo = MagicMock()
    repo.realized_pnl_split.return_value = {
        "short_term": Decimal(str(st)),
        "long_term": Decimal(str(lt)),
    }
    repo.section_1256_pnl.return_value = Decimal(str(sec1256_realized))
    repo.section_1256_mtm_pnl.return_value = Decimal(str(sec1256_mtm))
    repo.wash_sale_disallowed_total.return_value = Decimal(str(disallowed))
    return repo


def test_after_tax_includes_section_1256_mtm_gain():
    repo = _repo(sec1256_mtm=1000)
    out = compute_after_tax(repo, Period.for_year(2025), account=None, brackets=_brackets())
    expected_tax = Decimal("1000") * (Decimal("0.6") * Decimal("0.15") + Decimal("0.4") * Decimal("0.32"))
    assert out.section_1256_mtm_pnl == Decimal("1000")
    assert abs(out.estimated_tax_bill - expected_tax) < Decimal("0.01")


def test_after_tax_includes_section_1256_mtm_loss():
    repo = _repo(sec1256_mtm=-500, sec1256_realized=300)
    out = compute_after_tax(repo, Period.for_year(2025), account=None, brackets=_brackets())
    # Net §1256: 300 realized + −500 MTM = −200 → no positive amount → tax = 0
    assert out.section_1256_mtm_pnl == Decimal("-500")
    assert out.section_1256_pnl == Decimal("300")
    assert out.estimated_tax_bill == Decimal("0")


def test_after_tax_caveat_mentions_mtm_source():
    repo = _repo(sec1256_mtm=100)
    out = compute_after_tax(repo, Period.for_year(2025), account=None, brackets=_brackets())
    joined = " ".join(out.caveats).lower()
    assert "mark" in joined or "mtm" in joined or "§1256(a)" in joined
    # The stale "open §1256 positions Dec 31 not marked-to-market" caveat must be gone.
    assert "not marked-to-market" not in joined


def test_after_tax_zero_mtm_preserves_legacy_behavior():
    repo = _repo(st=1000, lt=2000)
    out = compute_after_tax(repo, Period.for_year(2025), account=None, brackets=_brackets())
    # MTM = 0; legacy outputs should be unchanged.
    assert out.section_1256_mtm_pnl == Decimal("0")
    # ST tax = 1000 * 0.32 = 320; LT tax = 2000 * 0.15 = 300; total = 620.
    assert out.estimated_tax_bill == Decimal("620")
