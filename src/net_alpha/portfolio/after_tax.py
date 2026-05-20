"""After-tax realized P&L + tax-drag computation.

Pure function. Reads from Repository (split realized P&L, §1256 net P&L,
wash-sale disallowed total). Returns an AfterTaxBreakdown.

Out-of-scope simplifications (caveats surface inline):
- MAGI-based NIIT threshold ($200K single / $250K MFJ)
- Qualified dividends, §199A, AMT
- Per-year historical brackets for Lifetime period
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel

from net_alpha.portfolio.carryforward import Carryforward, ordinary_loss_cap
from net_alpha.portfolio.tax_planner import TaxBrackets

_NIIT_RATE = Decimal("0.038")
_LT_FRAC = Decimal("0.60")
_ST_FRAC = Decimal("0.40")
_RATE_PRECISION = Decimal("0.001")


@dataclass(frozen=True)
class Period:
    kind: str  # "ytd" | "year" | "lifetime"
    label: str
    year: int | None = None

    @classmethod
    def ytd(cls, year: int) -> Period:
        return cls(kind="ytd", label=f"YTD {year}", year=year)

    @classmethod
    def for_year(cls, year: int) -> Period:
        return cls(kind="year", label=str(year), year=year)

    @classmethod
    def lifetime(cls) -> Period:
        return cls(kind="lifetime", label="Lifetime", year=None)


class AfterTaxBreakdown(BaseModel):
    pre_tax_realized_pnl: Decimal
    estimated_tax_bill: Decimal
    after_tax_realized_pnl: Decimal
    tax_drag_dollar: Decimal
    tax_drag_pct: Decimal

    short_term_pnl: Decimal
    long_term_pnl: Decimal
    section_1256_pnl: Decimal
    section_1256_lt_portion: Decimal
    section_1256_st_portion: Decimal
    section_1256_mtm_pnl: Decimal = Decimal("0")
    section_1256_mtm_lt_portion: Decimal = Decimal("0")
    section_1256_mtm_st_portion: Decimal = Decimal("0")

    wash_sale_disallowed_total: Decimal
    wash_sale_marginal_cost: Decimal
    # Rev. Rul. 2008-5: replacement lot in an IRA / Roth / 401(k) / HSA means
    # §1091(d) basis rollover is impossible — the loss is permanently lost.
    # ``wash_sale_deferred_total`` rolls into the replacement lot's basis (future
    # tax savings); ``wash_sale_permanent_total`` does not.
    wash_sale_deferred_total: Decimal = Decimal("0")
    wash_sale_permanent_total: Decimal = Decimal("0")

    effective_tax_rate: Decimal

    period_label: str
    account_filter: str | None
    tax_brackets_used: TaxBrackets
    caveats: list[str]


def compute_after_tax(
    repo,
    period: Period,
    brackets: TaxBrackets | None = None,
    carryforward: Carryforward | None = None,
    *,
    accounts: Sequence[str] | None = None,
) -> AfterTaxBreakdown:
    if brackets is None:
        raise ValueError("compute_after_tax requires `brackets`")
    account_filter_label: str | None = ", ".join(accounts) if accounts else None

    pnl = repo.realized_pnl_split(period, accounts=accounts or None)
    st_pnl: Decimal = pnl["short_term"]
    lt_pnl: Decimal = pnl["long_term"]
    sec1256_pnl: Decimal = repo.section_1256_pnl(period, accounts=accounts or None)
    sec1256_mtm: Decimal = repo.section_1256_mtm_pnl(period, accounts=accounts or None)
    disallowed_by_kind = (
        repo.wash_sale_disallowed_by_kind(period, accounts=accounts or None)
        if hasattr(repo, "wash_sale_disallowed_by_kind")
        else {
            "deferred": repo.wash_sale_disallowed_total(period, accounts=accounts or None),
            "permanent_ira": Decimal("0"),
        }
    )
    disallowed_deferred = disallowed_by_kind.get("deferred", Decimal("0"))
    disallowed_permanent = disallowed_by_kind.get("permanent_ira", Decimal("0"))
    disallowed: Decimal = disallowed_deferred + disallowed_permanent

    cf = carryforward or Carryforward(st=Decimal("0"), lt=Decimal("0"), source="none")

    # Apply carryforward against same-bucket P&L first; surplus crosses
    # categories per §1212(b)(1)(B). Sign convention: cf.st / cf.lt are
    # non-negative magnitudes (loss numbers); subtracting them reduces gains.
    st_after_cf = st_pnl - cf.st
    lt_after_cf = lt_pnl - cf.lt

    if st_after_cf < 0 and lt_after_cf > 0:
        absorbed = min(-st_after_cf, lt_after_cf)
        st_after_cf += absorbed
        lt_after_cf -= absorbed
    elif lt_after_cf < 0 and st_after_cf > 0:
        absorbed = min(-lt_after_cf, st_after_cf)
        lt_after_cf += absorbed
        st_after_cf -= absorbed

    st_pnl = st_after_cf
    lt_pnl = lt_after_cf

    sec1256_total = sec1256_pnl + sec1256_mtm
    sec1256_lt = sec1256_total * _LT_FRAC
    sec1256_st = sec1256_total * _ST_FRAC
    sec1256_mtm_lt = sec1256_mtm * _LT_FRAC
    sec1256_mtm_st = sec1256_mtm * _ST_FRAC

    total_st = st_pnl + sec1256_st
    total_lt = lt_pnl + sec1256_lt

    st_tax = max(Decimal("0"), total_st) * brackets.federal_marginal_rate
    lt_tax = max(Decimal("0"), total_lt) * brackets.ltcg_rate
    state_tax = max(Decimal("0"), total_st + total_lt) * brackets.state_marginal_rate
    niit = max(Decimal("0"), total_st + total_lt) * _NIIT_RATE if brackets.niit_enabled else Decimal("0")

    tax_bill = st_tax + lt_tax + state_tax + niit
    pre_tax = st_pnl + lt_pnl + sec1256_pnl + sec1256_mtm
    after_tax = pre_tax - tax_bill

    # §1211(b) ordinary-loss-cap benefit. Mirror engine/lot_selector._compute_after_tax
    # so the sim's Lot Strategy Comparison and the Tax Performance tab agree on
    # the same calc when both have net loss. Up to $3K ($1.5K MFS) of net loss
    # offsets ordinary income at federal_marginal_rate.
    loss_residue = max(Decimal("0"), -(total_st + total_lt))
    cap_used = min(loss_residue, ordinary_loss_cap(getattr(brackets, "filing_status", None)))
    loss_benefit = cap_used * brackets.federal_marginal_rate
    after_tax = after_tax + loss_benefit
    drag_dollar = pre_tax - after_tax  # equals tax_bill when pre_tax > 0; 0 when pre_tax <= 0

    # For losses or zero P&L: after_tax == pre_tax, so drag is 0
    # But if pre_tax < 0 and tax_bill == 0, drag_dollar = 0 naturally
    # since after_tax = pre_tax - 0 = pre_tax; drag = pre_tax - pre_tax = 0.
    drag_pct = (drag_dollar / pre_tax).quantize(_RATE_PRECISION) if pre_tax > 0 else Decimal("0")

    effective_rate = (tax_bill / pre_tax).quantize(_RATE_PRECISION) if pre_tax > 0 else Decimal("0")
    wash_marginal_cost = disallowed * brackets.federal_marginal_rate

    caveats = [
        "Estimate using your configured marginal rates — not a tax filing.",
        f"NIIT applied at 3.8% above MAGI threshold ($200K single / $250K MFJ) "
        f"when enabled (currently: {'on' if brackets.niit_enabled else 'off'}).",
        "§1256 contracts open Dec 31 are marked to fair-market-value per IRC §1256(a). "
        "Year-end FMV is sourced from Yahoo (option closes) with a Black-Scholes fallback "
        "for thin-volume strikes; verify against your 1099-B / Form 6781 before filing.",
        "Wash-sale 'deferred tax savings' = tax savings deferred (not lost) — basis rolls into the replacement lot.",
    ]
    if disallowed_permanent > 0:
        caveats.append(
            "Permanently disallowed (Rev. Rul. 2008-5): a wash-sale replacement leg in a "
            "tax-advantaged account (IRA / Roth / 401(k) / HSA) blocks the §1091(d) basis "
            "rollover — the disallowed loss is gone for good, not deferred."
        )
    if period.kind == "lifetime":
        caveats.append(
            "Lifetime period uses currently configured rates for all historical years; "
            "bracket changes are not retro-applied."
        )
    if cf.st > 0 or cf.lt > 0:
        caveats.append(f"Carryforward applied: ST ${cf.st:,.2f} + LT ${cf.lt:,.2f} (source: {cf.source}).")

    return AfterTaxBreakdown(
        pre_tax_realized_pnl=pre_tax,
        estimated_tax_bill=tax_bill,
        after_tax_realized_pnl=after_tax,
        tax_drag_dollar=drag_dollar,
        tax_drag_pct=drag_pct,
        short_term_pnl=st_pnl,
        long_term_pnl=lt_pnl,
        section_1256_pnl=sec1256_pnl,
        section_1256_lt_portion=sec1256_lt,
        section_1256_st_portion=sec1256_st,
        section_1256_mtm_pnl=sec1256_mtm,
        section_1256_mtm_lt_portion=sec1256_mtm_lt,
        section_1256_mtm_st_portion=sec1256_mtm_st,
        wash_sale_disallowed_total=disallowed,
        wash_sale_marginal_cost=wash_marginal_cost,
        wash_sale_deferred_total=disallowed_deferred,
        wash_sale_permanent_total=disallowed_permanent,
        effective_tax_rate=effective_rate,
        period_label=period.label,
        account_filter=account_filter_label,
        tax_brackets_used=brackets,
        caveats=caveats,
    )
