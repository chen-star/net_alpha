"""Regression test: compute_after_tax applies §1211(b) ordinary-loss-cap benefit.

The engine path (lot_selector._compute_after_tax) already applies this.
The Tax Performance path (portfolio.after_tax.compute_after_tax) must too,
otherwise net-loss years show after_tax == pre_tax — losing the marginal-rate
credit on up to $3,000 of ordinary loss offset per IRC §1211(b).
"""

from __future__ import annotations

from decimal import Decimal

from net_alpha.portfolio.after_tax import Period, compute_after_tax
from net_alpha.portfolio.tax_planner import TaxBrackets


def _brackets(*, filing_status: str = "single", niit: bool = False) -> TaxBrackets:
    """Match the style in test_after_tax.py — niit off keeps loss arithmetic clean."""
    return TaxBrackets(
        filing_status=filing_status,
        state="",
        federal_marginal_rate=Decimal("0.35"),
        state_marginal_rate=Decimal("0"),
        ltcg_rate=Decimal("0.15"),
        qualified_div_rate=Decimal("0.15"),
        niit_enabled=niit,
    )


class _StubRepo:
    """Mirror tests/portfolio/test_after_tax.py::_StubRepo."""

    def __init__(
        self,
        *,
        st: Decimal = Decimal("0"),
        lt: Decimal = Decimal("0"),
        s1256: Decimal = Decimal("0"),
        s1256_mtm: Decimal = Decimal("0"),
        disallowed: Decimal = Decimal("0"),
    ):
        self._st = st
        self._lt = lt
        self._s1256 = s1256
        self._s1256_mtm = s1256_mtm
        self._disallowed = disallowed

    def realized_pnl_split(self, period, accounts=None):
        return {"short_term": self._st, "long_term": self._lt}

    def section_1256_pnl(self, period, accounts=None):
        return self._s1256

    def section_1256_mtm_pnl(self, period, accounts=None):
        return self._s1256_mtm

    def wash_sale_disallowed_total(self, period, accounts=None):
        return self._disallowed


def _ytd() -> Period:
    return Period.ytd(2026)


def test_loss_below_cap_yields_marginal_rate_benefit():
    """ST loss $1,500 (below $3K cap) → benefit = $1,500 × 0.35 = $525.

    After-tax = -$1,500 + $525 = -$975.
    """
    repo = _StubRepo(st=Decimal("-1500"))
    bd = compute_after_tax(repo, _ytd(), _brackets())
    assert bd.pre_tax_realized_pnl == Decimal("-1500")
    assert bd.estimated_tax_bill == Decimal("0")
    assert bd.after_tax_realized_pnl == Decimal("-975.00"), (
        f"Expected -975 (loss benefit applied), got {bd.after_tax_realized_pnl}"
    )


def test_loss_above_cap_caps_benefit_at_3k():
    """ST loss $5,000 (above $3K cap) → benefit capped: $3,000 × 0.35 = $1,050.

    After-tax = -$5,000 + $1,050 = -$3,950.
    """
    repo = _StubRepo(st=Decimal("-5000"))
    bd = compute_after_tax(repo, _ytd(), _brackets())
    assert bd.after_tax_realized_pnl == Decimal("-3950.00"), (
        f"Cap should limit benefit; got {bd.after_tax_realized_pnl}"
    )


def test_net_gain_no_loss_benefit_applied():
    """Net $1,000 gain → no §1211(b) benefit; after-tax = pre_tax - tax_bill."""
    repo = _StubRepo(st=Decimal("1000"))
    bd = compute_after_tax(repo, _ytd(), _brackets())
    assert bd.pre_tax_realized_pnl == Decimal("1000")
    # st_tax = 1000 * 0.35 = 350 ; niit off, state 0 → tax_bill = 350
    assert bd.estimated_tax_bill == Decimal("350")
    # No loss benefit added; after-tax is just pre_tax - tax_bill.
    assert bd.after_tax_realized_pnl == Decimal("1000") - bd.estimated_tax_bill


def test_loss_mfs_filing_status_uses_1500_cap():
    """MFS cap is $1,500 (half of single's $3K), per §1211(b).

    ST loss $5,000, fed_rate 0.35 → benefit = $1,500 × 0.35 = $525.
    After-tax = -$5,000 + $525 = -$4,475.
    """
    repo = _StubRepo(st=Decimal("-5000"))
    bd = compute_after_tax(repo, _ytd(), _brackets(filing_status="mfs"))
    assert bd.after_tax_realized_pnl == Decimal("-4475.00"), (
        f"MFS cap should yield -4475; got {bd.after_tax_realized_pnl}"
    )
