from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

import net_alpha.db.tables as _tables  # noqa: F401 — registers all SQLModel table classes
from net_alpha.db.migrations import migrate, set_schema_version


def _v10_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        # Simulate a pre-v11 db: drop the new tables/columns the v11 migration
        # is supposed to add, then stamp version 10.
        session.exec(text("DROP TABLE IF EXISTS exempt_matches"))
        session.exec(text("DROP TABLE IF EXISTS section_1256_classifications"))
        session.exec(text("ALTER TABLE trades DROP COLUMN is_section_1256"))
        session.exec(text("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', '10')"))
        session.commit()
    return engine


def test_migration_v10_to_v11_creates_exempt_matches_table():
    engine = _v10_engine()
    with Session(engine) as session:
        migrate(session)
        rows = session.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name='exempt_matches'")).all()
        assert len(rows) == 1


def test_migration_v10_to_v11_creates_section_1256_classifications_table():
    engine = _v10_engine()
    with Session(engine) as session:
        migrate(session)
        rows = session.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name='section_1256_classifications'")).all()
        assert len(rows) == 1


def test_migration_v10_to_v11_adds_is_section_1256_column():
    engine = _v10_engine()
    with Session(engine) as session:
        migrate(session)
        cols = session.exec(text("PRAGMA table_info(trades)")).all()
        names = [c[1] for c in cols]
        assert "is_section_1256" in names


def test_migration_v10_to_v11_stamps_universe_hash():
    engine = _v10_engine()
    with Session(engine) as session:
        migrate(session)
        row = session.exec(text("SELECT value FROM meta WHERE key='section_1256_universe_hash'")).first()
        assert row is not None and row[0]


def test_migration_v10_to_v11_idempotent():
    engine = _v10_engine()
    with Session(engine) as session:
        migrate(session)
    with Session(engine) as session:
        migrate(session)
