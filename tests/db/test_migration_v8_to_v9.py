# tests/db/test_migration_v8_to_v9.py
from sqlalchemy import create_engine, text
from sqlmodel import Session

from net_alpha.db.migrations import (
    CURRENT_SCHEMA_VERSION,
    get_schema_version,
    migrate,
    set_schema_version,
)


def _bootstrap_v8(engine):
    with Session(engine) as s:
        s.exec(text("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"))
        s.exec(text("CREATE TABLE accounts (id INTEGER PRIMARY KEY, broker TEXT, label TEXT)"))
        s.commit()
        set_schema_version(s, 8)


def test_migrate_v8_to_v9_creates_user_preferences():
    engine = create_engine("sqlite:///:memory:")
    _bootstrap_v8(engine)

    with Session(engine) as s:
        migrate(s)
        assert get_schema_version(s) == CURRENT_SCHEMA_VERSION
        rows = s.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'")).all()
        assert len(rows) == 1


def test_migrate_v9_idempotent():
    engine = create_engine("sqlite:///:memory:")
    _bootstrap_v8(engine)

    with Session(engine) as s:
        migrate(s)
        migrate(s)  # second run must not raise
        assert get_schema_version(s) == 9
