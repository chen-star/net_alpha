"""compute_after_tax surfaces permanent vs deferred disallowances separately."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlmodel import SQLModel, create_engine

from net_alpha.db.repository import Repository
from net_alpha.engine.recompute import recompute_all_violations
from net_alpha.models.domain import ImportRecord, Trade
from net_alpha.portfolio.after_tax import Period, compute_after_tax
from net_alpha.portfolio.tax_planner import TaxBrackets


@pytest.fixture
def repo(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/v2.db")
    SQLModel.metadata.create_all(eng)
    return Repository(eng)


@pytest.fixture
def brackets():
    return TaxBrackets(
        filing_status="single",
        state="",
        federal_marginal_rate=Decimal("0.32"),
        state_marginal_rate=Decimal("0.05"),
        ltcg_rate=Decimal("0.15"),
        qualified_div_rate=Decimal("0.15"),
        niit_enabled=False,
    )


def _seed_taxable_to_roth_wash(repo):
    taxable = repo.get_or_create_account("schwab", "personal")
    roth = repo.get_or_create_account("schwab", "roth")
    repo.set_account_type(broker="schwab", label="roth", type_="roth_ira")

    rec_t = ImportRecord(
        account_id=taxable.id,
        csv_filename="t.csv",
        csv_sha256="ht",
        imported_at=datetime(2026, 4, 25),
        trade_count=0,
    )
    rec_r = ImportRecord(
        account_id=roth.id,
        csv_filename="r.csv",
        csv_sha256="hr",
        imported_at=datetime(2026, 4, 25),
        trade_count=0,
    )
    sell = Trade(
        account=taxable.display(),
        date=date(2024, 6, 1),
        ticker="TSLA",
        action="Sell",
        quantity=10,
        proceeds=1500.0,
        cost_basis=2000.0,
    )
    buy = Trade(
        account=roth.display(),
        date=date(2024, 6, 5),
        ticker="TSLA",
        action="Buy",
        quantity=10,
        cost_basis=1700.0,
    )
    repo.add_import(taxable, rec_t, [sell])
    repo.add_import(roth, rec_r, [buy])
    recompute_all_violations(repo, etf_pairs={})


def test_after_tax_separates_permanent_from_deferred(repo, brackets):
    _seed_taxable_to_roth_wash(repo)
    result = compute_after_tax(repo, Period.for_year(2024), brackets=brackets)

    # All disallowance in this scenario is permanent (Rev. Rul. 2008-5).
    assert result.wash_sale_disallowed_total == Decimal("500.0")
    assert result.wash_sale_permanent_total == Decimal("500.0")
    assert result.wash_sale_deferred_total == Decimal("0.0")


def test_after_tax_caveat_mentions_permanent_when_present(repo, brackets):
    _seed_taxable_to_roth_wash(repo)
    result = compute_after_tax(repo, Period.for_year(2024), brackets=brackets)

    # When permanent disallowances exist, the caveat must call out the
    # permanent-vs-deferred distinction (Rev. Rul. 2008-5).
    assert any("Rev. Rul. 2008-5" in c or "permanent" in c.lower() for c in result.caveats)


def test_after_tax_deferred_only_no_permanent_field(repo, brackets):
    """All-deferred case: permanent_total = 0, deferred_total = total."""
    taxable = repo.get_or_create_account("schwab", "personal")
    rec = ImportRecord(
        account_id=taxable.id,
        csv_filename="t.csv",
        csv_sha256="ht",
        imported_at=datetime(2026, 4, 25),
        trade_count=0,
    )
    sell = Trade(
        account=taxable.display(),
        date=date(2024, 6, 1),
        ticker="TSLA",
        action="Sell",
        quantity=10,
        proceeds=1500.0,
        cost_basis=2000.0,
    )
    buy = Trade(
        account=taxable.display(),
        date=date(2024, 6, 5),
        ticker="TSLA",
        action="Buy",
        quantity=10,
        cost_basis=1700.0,
    )
    repo.add_import(taxable, rec, [sell, buy])
    recompute_all_violations(repo, etf_pairs={})

    result = compute_after_tax(repo, Period.for_year(2024), brackets=brackets)
    assert result.wash_sale_disallowed_total == Decimal("500.0")
    assert result.wash_sale_deferred_total == Decimal("500.0")
    assert result.wash_sale_permanent_total == Decimal("0.0")
