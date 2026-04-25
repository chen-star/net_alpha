import pytest
from sqlmodel import SQLModel, create_engine

from net_alpha.db.repository import Repository


@pytest.fixture
def repo(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/v2.db")
    SQLModel.metadata.create_all(eng)
    return Repository(eng)


def test_get_or_create_account_creates_when_missing(repo):
    a = repo.get_or_create_account("schwab", "personal")
    assert a.id is not None
    assert a.display() == "schwab/personal"


def test_get_or_create_account_is_idempotent(repo):
    a1 = repo.get_or_create_account("schwab", "personal")
    a2 = repo.get_or_create_account("schwab", "personal")
    assert a1.id == a2.id


def test_get_account_returns_none_when_missing(repo):
    assert repo.get_account("schwab", "ghost") is None


def test_get_account_returns_existing(repo):
    repo.get_or_create_account("schwab", "personal")
    a = repo.get_account("schwab", "personal")
    assert a is not None and a.label == "personal"


def test_list_accounts_returns_all(repo):
    repo.get_or_create_account("schwab", "personal")
    repo.get_or_create_account("schwab", "roth")
    accts = repo.list_accounts()
    assert {a.label for a in accts} == {"personal", "roth"}


def test_list_imports_empty(repo):
    assert repo.list_imports() == []


def test_get_import_returns_none_when_missing(repo):
    assert repo.get_import(999) is None
