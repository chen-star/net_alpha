from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from net_alpha.models.domain import Trade
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
