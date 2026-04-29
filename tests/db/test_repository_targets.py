from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from net_alpha.db.migrations import migrate
from net_alpha.db.repository import Repository
from net_alpha.targets.models import TargetUnit


@pytest.fixture
def repo() -> Repository:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        migrate(s)
    return Repository(engine)


def test_upsert_creates_then_updates(repo: Repository):
    # Create.
    t1 = repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    assert t1.symbol == "HIMS"
    assert t1.target_amount == Decimal("1000")
    assert t1.target_unit == TargetUnit.USD
    first_created = t1.created_at

    # Update — same symbol, different amount.
    t2 = repo.upsert_target("HIMS", Decimal("2000"), TargetUnit.SHARES)
    assert t2.target_amount == Decimal("2000")
    assert t2.target_unit == TargetUnit.SHARES
    assert t2.created_at == first_created  # preserved
    assert t2.updated_at >= first_created   # bumped


def test_get_target_returns_none_for_unknown(repo: Repository):
    assert repo.get_target("NOPE") is None


def test_list_targets_returns_alphabetical(repo: Repository):
    repo.upsert_target("VOO", Decimal("10000"), TargetUnit.USD)
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.upsert_target("MSFT", Decimal("5000"), TargetUnit.USD)
    syms = [t.symbol for t in repo.list_targets()]
    assert syms == ["HIMS", "MSFT", "VOO"]


def test_delete_target(repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    assert repo.delete_target("HIMS") is True
    assert repo.delete_target("HIMS") is False  # already gone
    assert repo.get_target("HIMS") is None


def test_symbol_uppercased(repo: Repository):
    t = repo.upsert_target("hims", Decimal("1000"), TargetUnit.USD)
    assert t.symbol == "HIMS"
    assert repo.get_target("HIMS").target_amount == Decimal("1000")
    assert repo.get_target("hims").target_amount == Decimal("1000")  # case-insensitive lookup
