"""After-tax realized P&L + tax-drag computation.

Pure function. Reads from Repository (split realized P&L, §1256 net P&L,
wash-sale disallowed total). Returns an AfterTaxBreakdown.

Out-of-scope simplifications (caveats surface inline):
- MAGI-based NIIT threshold ($200K single / $250K MFJ)
- Qualified dividends, §199A, AMT
- Per-year historical brackets for Lifetime period
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel

from net_alpha.portfolio.carryforward import Carryforward
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

    wash_sale_disallowed_total: Decimal
    wash_sale_marginal_cost: Decimal

    effective_tax_rate: Decimal

    period_label: str
    account_filter: str | None
    tax_brackets_used: TaxBrackets
    caveats: list[str]


def compute_after_tax(
    repo,
    period: Period,
    account: str | None,
    brackets: TaxBrackets,
    carryforward: Carryforward | None = None,
) -> AfterTaxBreakdown:
    pnl = repo.realized_pnl_split(period, account)
    st_pnl: Decimal = pnl["short_term"]
    lt_pnl: Decimal = pnl["long_term"]
    sec1256_pnl: Decimal = repo.section_1256_pnl(period, account)
    disallowed: Decimal = repo.wash_sale_disallowed_total(period, account)

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

    sec1256_lt = sec1256_pnl * _LT_FRAC
    sec1256_st = sec1256_pnl * _ST_FRAC

    total_st = st_pnl + sec1256_st
    total_lt = lt_pnl + sec1256_lt

    st_tax = max(Decimal("0"), total_st) * brackets.federal_marginal_rate
    lt_tax = max(Decimal("0"), total_lt) * brackets.ltcg_rate
    state_tax = max(Decimal("0"), total_st + total_lt) * brackets.state_marginal_rate
    niit = max(Decimal("0"), total_st + total_lt) * _NIIT_RATE if brackets.niit_enabled else Decimal("0")

    tax_bill = st_tax + lt_tax + state_tax + niit
    pre_tax = st_pnl + lt_pnl + sec1256_pnl
    after_tax = pre_tax - tax_bill
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
        "Open §1256 positions Dec 31 not marked-to-market — see 1099-B / Form 6781 separately.",
        "Wash-sale 'deferred tax savings' = tax savings deferred (not lost) — basis rolls into the replacement lot.",
    ]
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
        wash_sale_disallowed_total=disallowed,
        wash_sale_marginal_cost=wash_marginal_cost,
        effective_tax_rate=effective_rate,
        period_label=period.label,
        account_filter=account,
        tax_brackets_used=brackets,
        caveats=caveats,
    )
