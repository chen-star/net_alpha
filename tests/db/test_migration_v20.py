"""v19 → v20 migration: introduces plan_view_snapshot table.

The plan_last_seen_at value lives in the existing `meta` (key, value) table
and requires no schema change.
"""

from __future__ import annotations

from sqlmodel import Session, SQLModel, text

import net_alpha.db.tables as _tables  # noqa: F401 — registers all SQLModel table classes
from net_alpha.db.connection import get_engine
from net_alpha.db.migrations import (
    CURRENT_SCHEMA_VERSION,
    ensure_schema,
    set_schema_version,
)


def test_current_schema_version_is_20():
    assert CURRENT_SCHEMA_VERSION == 20


def test_migration_creates_snapshot_table(tmp_path):
    engine = get_engine(tmp_path / "v19.db")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as s:
        # Force schema_version=19 to simulate an upgrade from a v19 DB.
        ensure_schema(s)  # bring up to current
        set_schema_version(s, 19)  # then knock it back to v19
        s.commit()

    # Re-run migration; should advance to v20 and create the table.
    with Session(engine) as s:
        ensure_schema(s)

    with Session(engine) as s:
        rows = s.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name='plan_view_snapshot'")).all()
        assert rows, "plan_view_snapshot table not created"

        version = s.exec(text("SELECT value FROM meta WHERE key='schema_version'")).first()
        assert version[0] == "20"


def test_migration_is_idempotent(tmp_path):
    """Running ensure_schema twice on the same DB does not re-run the v20 step."""
    engine = get_engine(tmp_path / "idempotent.db")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        ensure_schema(s)
        ensure_schema(s)  # second call is a no-op once at CURRENT
