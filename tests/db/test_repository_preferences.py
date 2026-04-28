# tests/db/test_repository_preferences.py
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlmodel import SQLModel

from net_alpha.db.repository import Repository
from net_alpha.models.preferences import AccountPreference


@pytest.fixture
def repo():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Repository(engine)


def _seed_account(repo: Repository, label: str = "Tax") -> int:
    acct = repo.get_or_create_account("Schwab", label)
    return acct.id


def test_get_user_preference_missing_returns_none(repo):
    aid = _seed_account(repo)
    assert repo.get_user_preference(aid) is None


def test_upsert_user_preference_creates_row(repo):
    aid = _seed_account(repo)
    now = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
    repo.upsert_user_preference(
        AccountPreference(
            account_id=aid,
            profile="options",
            density="tax",
            updated_at=now,
        )
    )
    pref = repo.get_user_preference(aid)
    assert pref is not None
    assert pref.profile == "options"
    assert pref.density == "tax"


def test_upsert_user_preference_updates_existing(repo):
    aid = _seed_account(repo)
    now = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
    repo.upsert_user_preference(
        AccountPreference(account_id=aid, profile="active", density="comfortable", updated_at=now)
    )
    repo.upsert_user_preference(
        AccountPreference(account_id=aid, profile="conservative", density="compact", updated_at=now)
    )
    pref = repo.get_user_preference(aid)
    assert pref.profile == "conservative"
    assert pref.density == "compact"


def test_list_user_preferences_returns_all(repo):
    a = _seed_account(repo, "Tax")
    b = _seed_account(repo, "Roth")
    now = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
    repo.upsert_user_preference(
        AccountPreference(account_id=a, profile="active", density="comfortable", updated_at=now)
    )
    repo.upsert_user_preference(AccountPreference(account_id=b, profile="options", density="tax", updated_at=now))
    out = repo.list_user_preferences()
    by_id = {p.account_id: p for p in out}
    assert by_id[a].profile == "active"
    assert by_id[b].profile == "options"
