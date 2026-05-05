from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from net_alpha.db.migrations import migrate
from net_alpha.db.repository import Repository
from net_alpha.targets.models import TargetUnit


@pytest.fixture
def repo() -> Repository:
    # StaticPool keeps a single connection so PRAGMA foreign_keys persists
    # across all sessions — required for SQLite FK cascade tests.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_fk(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        migrate(s)
        # SQLModel.metadata.create_all builds position_target_tag without FK
        # ON DELETE CASCADE (ORM model has no cascade annotation). Drop and
        # recreate so the DB-level cascade fires when delete_target runs.
        s.exec(text("DROP TABLE IF EXISTS position_target_tag"))
        s.exec(
            text("""
            CREATE TABLE position_target_tag (
                target_symbol TEXT NOT NULL,
                tag           TEXT NOT NULL,
                PRIMARY KEY (target_symbol, tag),
                FOREIGN KEY (target_symbol)
                    REFERENCES position_targets(symbol)
                    ON DELETE CASCADE
            )
        """)
        )
        s.exec(text("CREATE INDEX IF NOT EXISTS ix_position_target_tag_tag ON position_target_tag(tag)"))
        s.commit()
    return Repository(engine)


def test_set_target_tags_creates_then_reads(repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.set_target_tags("HIMS", ["core", "income"])
    assert repo.list_target_tags("HIMS") == ("core", "income")


def test_set_target_tags_normalizes_and_dedupes(repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.set_target_tags("HIMS", ["Core", "INCOME", "core", "  income  "])
    assert repo.list_target_tags("HIMS") == ("core", "income")


def test_set_target_tags_replaces(repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.set_target_tags("HIMS", ["core", "income"])
    repo.set_target_tags("HIMS", ["spec"])
    assert repo.list_target_tags("HIMS") == ("spec",)


def test_set_target_tags_empty_clears(repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.set_target_tags("HIMS", ["core"])
    repo.set_target_tags("HIMS", [])
    assert repo.list_target_tags("HIMS") == ()


def test_set_target_tags_silently_drops_invalid(repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.set_target_tags("HIMS", ["core", "untagged", ""])
    assert repo.list_target_tags("HIMS") == ("core",)


def test_add_target_tag_idempotent(repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.add_target_tag("HIMS", "core")
    repo.add_target_tag("HIMS", "core")
    assert repo.list_target_tags("HIMS") == ("core",)


def test_add_target_tag_invalid_returns_false(repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    assert repo.add_target_tag("HIMS", "untagged") is False
    assert repo.list_target_tags("HIMS") == ()


def test_remove_target_tag_idempotent(repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.set_target_tags("HIMS", ["core"])
    repo.remove_target_tag("HIMS", "core")
    repo.remove_target_tag("HIMS", "core")  # already gone
    assert repo.list_target_tags("HIMS") == ()


def test_list_all_tags_dedup_alpha_sorted(repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.upsert_target("VOO", Decimal("10000"), TargetUnit.USD)
    repo.set_target_tags("HIMS", ["core", "income"])
    repo.set_target_tags("VOO", ["core", "etf"])
    assert repo.list_all_tags() == ("core", "etf", "income")


def test_cascade_delete_target_removes_tags(repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.set_target_tags("HIMS", ["core"])
    assert repo.delete_target("HIMS") is True
    assert repo.list_target_tags("HIMS") == ()


def test_set_target_tags_uppercases_symbol(repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.set_target_tags("hims", ["core"])  # lowercase input
    assert repo.list_target_tags("HIMS") == ("core",)
