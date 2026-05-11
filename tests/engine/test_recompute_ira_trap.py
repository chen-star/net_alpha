"""End-to-end: recompute persists kind='permanent_ira' when replacement is in IRA."""

from datetime import date, datetime

import pytest
from sqlmodel import SQLModel, create_engine

from net_alpha.db.repository import Repository
from net_alpha.engine.recompute import recompute_all_violations
from net_alpha.models.domain import ImportRecord, Trade


@pytest.fixture
def repo(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/v2.db")
    SQLModel.metadata.create_all(eng)
    return Repository(eng)


def test_recompute_marks_taxable_loss_into_roth_buy_as_permanent_ira(repo):
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

    vs = repo.all_violations()
    assert len(vs) == 1
    assert vs[0].kind == "permanent_ira"
    assert vs[0].loss_account == "schwab/personal"
    assert vs[0].buy_account == "schwab/roth"

    # Replacement lot in the Roth must have its purchase basis untouched (no §1091(d) rollover).
    roth_lots = [lot for lot in repo.all_lots() if lot.account == "schwab/roth"]
    assert len(roth_lots) == 1
    assert roth_lots[0].adjusted_basis == 1700.0
    assert roth_lots[0].tacked_acquired_date is None


def test_recompute_marks_same_taxable_match_as_deferred(repo):
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

    vs = repo.all_violations()
    assert len(vs) == 1
    assert vs[0].kind == "deferred"
