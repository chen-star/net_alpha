from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from net_alpha.models.domain import Section1256MTM, Trade
from net_alpha.portfolio.tax_planner import (
    MissingTaxConfig,
    PlannedTrade,
    TaxBrackets,
    project_year_end_tax,
)

_BRACKETS = TaxBrackets(
    filing_status="single",
    state="CA",
    federal_marginal_rate=Decimal("0.32"),
    state_marginal_rate=Decimal("0.093"),
    ltcg_rate=Decimal("0.15"),
    qualified_div_rate=Decimal("0.15"),
)


def test_tax_brackets_construct() -> None:
    b = TaxBrackets(
        filing_status="single",
        state="CA",
        federal_marginal_rate=Decimal("0.32"),
        state_marginal_rate=Decimal("0.093"),
        ltcg_rate=Decimal("0.15"),
        qualified_div_rate=Decimal("0.15"),
    )
    assert b.filing_status == "single"


def test_missing_tax_config_raises_when_brackets_none(repo) -> None:
    with pytest.raises(MissingTaxConfig):
        project_year_end_tax(repo=repo, year=2026, brackets=None)


def test_projection_zero_when_no_realized(repo) -> None:
    p = project_year_end_tax(repo=repo, year=2026, brackets=_BRACKETS)
    assert p.realized_st_gain == 0
    assert p.realized_lt_gain == 0
    assert p.federal_tax == 0
    assert p.state_tax == 0
    assert p.total_tax == 0


def test_projection_short_term_gain_taxed_ordinary_plus_state(
    repo,
    schwab_account,
    seed_import,
) -> None:
    today = date(2026, 5, 1)
    buy = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=10),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("1"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("100"),
    )
    sell = Trade(
        account=schwab_account.display(),
        date=today,
        ticker="UUUU",
        action="Sell",
        quantity=Decimal("1"),
        proceeds=Decimal("200"),
        cost_basis=Decimal("100"),
    )
    seed_import(repo, schwab_account, [buy, sell])

    p = project_year_end_tax(repo=repo, year=2026, brackets=_BRACKETS)
    assert p.realized_st_gain == Decimal("100")
    assert p.federal_tax == Decimal("32.00")
    assert p.state_tax == Decimal("9.30")
    assert p.total_tax == Decimal("41.30")


def test_projection_long_term_gain_taxed_ltcg_rate(
    repo,
    schwab_account,
    seed_import,
) -> None:
    today = date(2026, 5, 1)
    buy = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=400),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("1"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("100"),
    )
    sell = Trade(
        account=schwab_account.display(),
        date=today,
        ticker="UUUU",
        action="Sell",
        quantity=Decimal("1"),
        proceeds=Decimal("200"),
        cost_basis=Decimal("100"),
    )
    seed_import(repo, schwab_account, [buy, sell])

    p = project_year_end_tax(repo=repo, year=2026, brackets=_BRACKETS)
    assert p.realized_lt_gain == Decimal("100")
    assert p.federal_tax == Decimal("15.00")
    assert p.state_tax == Decimal("9.30")


def test_projection_planned_trade_adds_pnl(
    repo,
    schwab_account,
    seed_import,
    seed_lots,
) -> None:
    """Planned sell at a loss (price < avg_basis) reduces ST realized."""
    today = date(2026, 5, 1)
    # Buy 10 shares at $20/share total_basis=200, avg_basis=20/share
    buy = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=10),
        ticker="PLNX",
        action="Buy",
        quantity=Decimal("10"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("200"),
    )
    seed_import(repo, schwab_account, [buy])
    seed_lots(repo)
    # Planned sell at price=10 per share (below avg_basis of 20) => pnl=(10-20)*10=-100
    planned = [
        PlannedTrade(
            symbol="PLNX",
            account_id=schwab_account.id or 0,
            action="Sell",
            qty=Decimal("10"),
            price=Decimal("10"),
            on=date(2026, 6, 1),
        )
    ]
    p = project_year_end_tax(
        repo=repo,
        year=2026,
        brackets=_BRACKETS,
        planned_trades=planned,
    )
    # avg_basis = 200 / 10 = 20.0; pnl = (10 - 20) * 10 = -100
    assert p.realized_st_gain == Decimal("-100")
    # Tax on loss is 0 (clamped)
    assert p.federal_tax == Decimal("0")


def test_projection_emits_bracket_warning_when_st_swings_large(
    repo,
    schwab_account,
    seed_import,
) -> None:
    today = date(2026, 5, 1)
    buy = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=10),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("1"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("1000"),
    )
    sell = Trade(
        account=schwab_account.display(),
        date=today,
        ticker="UUUU",
        action="Sell",
        quantity=Decimal("1"),
        proceeds=Decimal("21000"),
        cost_basis=Decimal("1000"),
    )
    seed_import(repo, schwab_account, [buy, sell])
    p = project_year_end_tax(repo=repo, year=2026, brackets=_BRACKETS)
    assert any("bracket" in w.lower() for w in p.bracket_warnings)


def test_total_tax_equals_sum_of_displayed_components(
    repo,
    schwab_account,
    seed_import,
) -> None:
    """Header total = federal_tax + state_tax exactly (no rounding drift).

    Regression: previously ``total_tax = _quantize(federal + state)`` while
    ``federal_tax = _quantize(federal)`` and ``state_tax = _quantize(state)``,
    which could drift one cent — surfacing as e.g. $50 fed + $15 state ≠ $64 total.

    Under the standard _BRACKETS (fed 0.32 / state 0.093), a ST gain of $141.42
    yields fed_raw=45.2544 → 45.25, state_raw=13.15206 → 13.15. The sum of the
    raw values is 58.40646 → quantized to 58.41 (old, drifted), whereas the
    sum of the rounded components is 58.40 (new, matches the displayed total).
    """
    today = date(2026, 5, 1)
    buy = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=10),
        ticker="DRIFT",
        action="Buy",
        quantity=Decimal("100"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("1000"),
    )
    sell = Trade(
        account=schwab_account.display(),
        date=today,
        ticker="DRIFT",
        action="Sell",
        quantity=Decimal("100"),
        proceeds=Decimal("1141.42"),
        cost_basis=Decimal("1000"),
    )
    seed_import(repo, schwab_account, [buy, sell])
    p = project_year_end_tax(repo=repo, year=2026, brackets=_BRACKETS)
    assert p.federal_tax + p.state_tax == p.total_tax, (
        f"Drift: fed={p.federal_tax} + state={p.state_tax} != total={p.total_tax}"
    )


def test_projection_includes_section_1256_mtm_60_40_split(
    repo,
    schwab_account,
    seed_import,
) -> None:
    """§1256(a)(1) year-end MTM rows must flow into the projection's ST/LT.

    Without this, the headline projection card understates tax by ignoring
    open §1256 positions that get marked-to-market on Dec 31 each year.
    Tax Performance shows them — the projection card must agree.
    """
    today = date(2026, 5, 1)
    # Seed a placeholder taxable trade just so the year has any activity.
    buy = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=10),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("1"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("100"),
    )
    seed_import(repo, schwab_account, [buy])

    # Open SPX 4000C at year-end with $1,000 unrealized gain → 60/40 = $600 LT, $400 ST.
    repo.save_section_1256_mtm(
        [
            Section1256MTM(
                position_key=f"SPX|4000.0|2027-06-19|C|{schwab_account.display()}",
                tax_year=2026,
                last_business_day=date(2026, 12, 31),
                fmv=Decimal("1100"),
                basis_before=Decimal("100"),
                unrealized_pnl=Decimal("1000.00"),
                long_term_portion=Decimal("600.00"),
                short_term_portion=Decimal("400.00"),
                fmv_source="yahoo_close",
                ticker="SPX",
                account=schwab_account.display(),
            )
        ]
    )

    p = project_year_end_tax(repo=repo, year=2026, brackets=_BRACKETS)
    # §1256 LT (60%) taxed at ltcg_rate (15%); ST (40%) at ordinary (32% fed).
    # State (9.3%) taxes both at the same rate. UUUU buy contributes nothing.
    assert p.realized_lt_gain == Decimal("600.00")
    assert p.realized_st_gain == Decimal("400.00")
