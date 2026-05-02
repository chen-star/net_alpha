"""v7 → v8: adds cash_events table; trades.gross_cash_impact; imports.cash_event_count."""

from sqlalchemy import create_engine, text
from sqlmodel import Session, SQLModel

import net_alpha.db.tables as _tables  # noqa: F401 — registers all SQLModel table classes
from net_alpha.db.migrations import (
    CURRENT_SCHEMA_VERSION,
    _column_exists,
    _table_exists,
    migrate,
)


def test_v7_to_v8_creates_cash_events_table_and_new_columns():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        # Pretend the DB is at v7 (skip the fresh-DB short-circuit).
        s.exec(
            text("INSERT INTO meta(key, value) VALUES ('schema_version', '7') ON CONFLICT(key) DO UPDATE SET value='7'")
        )
        s.commit()
        migrate(s)
        s.commit()
        assert _table_exists(s, "cash_events")
        assert _column_exists(s, "trades", "gross_cash_impact")
        assert _column_exists(s, "imports", "cash_event_count")
        version = s.exec(text("SELECT value FROM meta WHERE key='schema_version'")).first()
        assert int(version[0]) == CURRENT_SCHEMA_VERSION


def test_current_schema_version_is_14():
    assert CURRENT_SCHEMA_VERSION == 14
