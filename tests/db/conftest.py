# tests/db/conftest.py
import pytest
from sqlalchemy import create_engine, text
from sqlmodel import Session, SQLModel

import net_alpha.db.tables as _tables  # noqa: F401 — registers all SQLModel table classes
from net_alpha.db.connection import init_db
from net_alpha.db.migrations import set_schema_version
from net_alpha.db.repository import Repository


@pytest.fixture
def memory_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def repo():
    """Repository over a fully-migrated in-memory DB (matches production shape)."""
    engine = create_engine("sqlite://")
    init_db(engine)
    return Repository(engine)


@pytest.fixture
def in_memory_session_at_v23():
    """Provide a session attached to a fresh in-memory DB that has been
    migrated up through schema v23 (just below the v24 migration under test).

    init_db runs all migrations up to CURRENT_SCHEMA_VERSION. To simulate
    "at v23" we then drop the v24 tables (if they exist as SQLModel-defined
    tables) and stamp schema_version back to 23. The v23→v24 migration is
    gated on _table_exists, so the verify_* / broker_position tables will
    be absent — exactly what the v24 test wants to assert against.
    """
    engine = create_engine("sqlite://")
    init_db(engine)
    with Session(engine) as session:
        for tbl in ("verify_finding", "verify_result", "broker_position"):
            session.exec(text(f"DROP TABLE IF EXISTS {tbl}"))
        set_schema_version(session, 23)
        yield session


@pytest.fixture
def in_memory_session_at_v25():
    """Session attached to a fresh in-memory DB stamped at schema v25
    (just below the v26 broker_label migration under test).

    init_db runs every migration up to CURRENT_SCHEMA_VERSION. We then
    drop the v26-added column from accounts (if present, simulated by
    re-creating the table without it) and stamp schema_version back to
    25 so the v25→v26 migration runs as if encountering a v25 DB.
    """
    engine = create_engine("sqlite://")
    init_db(engine)
    with Session(engine) as session:
        # Strip the v26 column by rebuilding the accounts table without it.
        # Use the v25 shape: (id, broker, label, type, created_at).
        cols = [r[1] for r in session.exec(text("PRAGMA table_info(accounts)")).all()]
        if "broker_label" in cols:
            session.exec(text("ALTER TABLE accounts DROP COLUMN broker_label"))
        set_schema_version(session, 25)
        session.commit()
        yield session
