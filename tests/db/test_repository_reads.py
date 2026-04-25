from datetime import date, datetime

import pytest
from sqlmodel import SQLModel, create_engine

from net_alpha.db.repository import Repository
from net_alpha.models.domain import ImportRecord, Trade


@pytest.fixture
def repo(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/v2.db")
    SQLModel.metadata.create_all(eng)
    r = Repository(eng)
    acct = r.get_or_create_account("schwab", "personal")
    rec = ImportRecord(
        account_id=acct.id, csv_filename="x.csv", csv_sha256="h", imported_at=datetime(2026, 4, 25), trade_count=0
    )
    trades = [
        Trade(
            account=acct.display(),
            date=date(2024, 1, 5),
            ticker="TSLA",
            action="Buy",
            quantity=10,
            cost_basis=2000.0,
        ),
        Trade(
            account=acct.display(),
            date=date(2024, 6, 1),
            ticker="TSLA",
            action="Sell",
            quantity=10,
            proceeds=1500.0,
            cost_basis=2000.0,
        ),
        Trade(
            account=acct.display(),
            date=date(2024, 6, 15),
            ticker="TSLA",
            action="Buy",
            quantity=10,
            cost_basis=1700.0,
        ),
    ]
    r.add_import(acct, rec, trades)
    return r


def test_all_trades_returns_inserted(repo):
    ts = repo.all_trades()
    assert len(ts) == 3


def test_trades_in_window_filters_by_date(repo):
    ts = repo.trades_in_window(date(2024, 5, 1), date(2024, 7, 1))
    dates = sorted(t.date for t in ts)
    assert dates == [date(2024, 6, 1), date(2024, 6, 15)]


def test_all_lots_initially_empty(repo):
    assert repo.all_lots() == []


def test_all_violations_initially_empty(repo):
    assert repo.all_violations() == []


def test_violations_for_year_initially_empty(repo):
    assert repo.violations_for_year(2024) == []


def test_trades_for_import(repo):
    summary = repo.list_imports()[0]
    ts = repo.trades_for_import(summary.id)
    assert len(ts) == 3
