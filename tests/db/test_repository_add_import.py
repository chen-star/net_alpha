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


def _trade(account: str, ticker: str, qty: float, basis: float = 1000.0):
    return Trade(account=account, date=date(2024, 1, 1), ticker=ticker,
                 action="Buy", quantity=qty, cost_basis=basis)


def test_add_import_inserts_account_record_and_trades(repo):
    acct = repo.get_or_create_account("schwab", "personal")
    rec = ImportRecord(account_id=acct.id, csv_filename="q1.csv", csv_sha256="h",
                       imported_at=datetime(2026, 4, 25), trade_count=0)
    trades = [_trade(acct.display(), "TSLA", 10), _trade(acct.display(), "AAPL", 5)]
    result = repo.add_import(acct, rec, trades)
    assert result.new_trades == 2
    assert result.duplicate_trades == 0
    assert result.import_id is not None


def test_existing_natural_keys_returns_set(repo):
    acct = repo.get_or_create_account("schwab", "personal")
    assert repo.existing_natural_keys(acct.id) == set()


def test_re_adding_same_trades_under_same_account_skips_dups(repo):
    acct = repo.get_or_create_account("schwab", "personal")
    rec1 = ImportRecord(account_id=acct.id, csv_filename="q1.csv", csv_sha256="h1",
                        imported_at=datetime(2026, 4, 25), trade_count=0)
    rec2 = ImportRecord(account_id=acct.id, csv_filename="q1_again.csv", csv_sha256="h2",
                        imported_at=datetime(2026, 4, 26), trade_count=0)
    trades = [_trade(acct.display(), "TSLA", 10), _trade(acct.display(), "AAPL", 5)]

    repo.add_import(acct, rec1, trades)

    # Caller is responsible for filtering with existing_natural_keys before add_import.
    keys = repo.existing_natural_keys(acct.id)
    new_trades = [t for t in trades if t.compute_natural_key() not in keys]
    result = repo.add_import(acct, rec2, new_trades)
    assert result.new_trades == 0
    assert result.duplicate_trades == 0  # caller already filtered them


def test_same_natural_key_in_different_account_is_independent(repo):
    a = repo.get_or_create_account("schwab", "personal")
    b = repo.get_or_create_account("schwab", "roth")
    rec_a = ImportRecord(account_id=a.id, csv_filename="a.csv", csv_sha256="h",
                         imported_at=datetime(2026, 4, 25), trade_count=0)
    rec_b = ImportRecord(account_id=b.id, csv_filename="b.csv", csv_sha256="h",
                         imported_at=datetime(2026, 4, 25), trade_count=0)
    repo.add_import(a, rec_a, [_trade(a.display(), "TSLA", 10)])
    result = repo.add_import(b, rec_b, [_trade(b.display(), "TSLA", 10)])
    assert result.new_trades == 1
