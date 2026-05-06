from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

import net_alpha.db.tables as _tables  # noqa: F401 — registers all SQLModel table classes
from net_alpha.db.migrations import (
    CURRENT_SCHEMA_VERSION,
    get_schema_version,
    migrate,
)


def test_v17_to_v18_creates_loss_carryforward_table():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        # Simulate a pre-v18 DB: drop the table and stamp v17
        session.exec(text("DROP TABLE loss_carryforward"))
        session.exec(text("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','17')"))
        session.commit()

        migrate(session)

        assert get_schema_version(session) == CURRENT_SCHEMA_VERSION
        assert CURRENT_SCHEMA_VERSION >= 18
        # Table now exists
        rows = session.exec(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='loss_carryforward'")
        ).all()
        assert len(rows) == 1


def test_v17_to_v18_idempotent():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.exec(text("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','17')"))
        session.commit()
        migrate(session)
        migrate(session)  # second call must not raise
        assert get_schema_version(session) == CURRENT_SCHEMA_VERSION
