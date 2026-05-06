from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from net_alpha.db.migrations import migrate
from net_alpha.db.repository import Repository


@pytest.fixture
def repo() -> Repository:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        migrate(s)
    return Repository(engine)


def test_get_returns_none_when_absent(repo: Repository):
    assert repo.get_carryforward_override(2025) is None


def test_upsert_then_get(repo: Repository):
    repo.upsert_carryforward_override(year=2025, st=Decimal("100"), lt=Decimal("50"), note="from 2024 1040")
    row = repo.get_carryforward_override(2025)
    assert row is not None
    assert row.st_amount == Decimal("100")
    assert row.lt_amount == Decimal("50")
    assert row.note == "from 2024 1040"
    assert row.source == "user"
    assert isinstance(row.updated_at, datetime)


def test_upsert_overwrites(repo: Repository):
    repo.upsert_carryforward_override(year=2025, st=Decimal("100"), lt=Decimal("0"))
    repo.upsert_carryforward_override(year=2025, st=Decimal("200"), lt=Decimal("0"))
    row = repo.get_carryforward_override(2025)
    assert row is not None
    assert row.st_amount == Decimal("200")


def test_delete_removes_override(repo: Repository):
    repo.upsert_carryforward_override(year=2025, st=Decimal("100"), lt=Decimal("0"))
    repo.delete_carryforward_override(2025)
    assert repo.get_carryforward_override(2025) is None


def test_all_overrides_returns_sorted_by_year(repo: Repository):
    repo.upsert_carryforward_override(year=2025, st=Decimal("1"), lt=Decimal("0"))
    repo.upsert_carryforward_override(year=2023, st=Decimal("3"), lt=Decimal("0"))
    repo.upsert_carryforward_override(year=2024, st=Decimal("2"), lt=Decimal("0"))
    rows = repo.all_carryforward_overrides()
    assert [r.year for r in rows] == [2023, 2024, 2025]
