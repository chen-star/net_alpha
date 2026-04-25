from datetime import date, datetime

import pytest
from sqlmodel import SQLModel, create_engine

from net_alpha.db.repository import Repository
from net_alpha.models.domain import ImportRecord, Trade


@pytest.fixture
def repo(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/v2.db")
    SQLModel.metadata.create_all(eng)
    return Repository(eng)


def test_remove_import_cascades_trades(repo):
    acct = repo.get_or_create_account("schwab", "personal")
    rec = ImportRecord(
        account_id=acct.id, csv_filename="x.csv", csv_sha256="h", imported_at=datetime(2026, 4, 25), trade_count=0
    )
    trades = [
        Trade(
            account=acct.display(),
            date=date(2024, 6, 1),
            ticker="TSLA",
            action="Sell",
            quantity=10,
            proceeds=1500,
            cost_basis=2000,
        ),
        Trade(
            account=acct.display(),
            date=date(2024, 6, 5),
            ticker="TSLA",
            action="Buy",
            quantity=10,
            cost_basis=1700,
        ),
    ]
    res = repo.add_import(acct, rec, trades)
    rm = repo.remove_import(res.import_id)
    assert rm.removed_trade_count == 2
    assert rm.recompute_window == (date(2024, 5, 2), date(2024, 7, 5))
    assert repo.all_trades() == []


def test_remove_import_returns_none_window_for_empty_import(repo):
    acct = repo.get_or_create_account("schwab", "personal")
    rec = ImportRecord(
        account_id=acct.id, csv_filename="empty.csv", csv_sha256="h", imported_at=datetime(2026, 4, 25), trade_count=0
    )
    res = repo.add_import(acct, rec, [])
    rm = repo.remove_import(res.import_id)
    assert rm.removed_trade_count == 0
    assert rm.recompute_window is None


def test_replace_violations_in_window_clears_then_writes(repo):
    repo.replace_violations_in_window(date(2024, 5, 1), date(2024, 7, 1), [])
    assert repo.all_violations() == []
