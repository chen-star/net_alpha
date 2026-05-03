from sqlalchemy import text
from sqlmodel import Session, create_engine

from net_alpha.db.migrations import CURRENT_SCHEMA_VERSION, get_schema_version, migrate


def test_v15_creates_dismissed_inbox_items():
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as s:
        s.exec(text("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"))
        s.exec(text("INSERT INTO meta(key, value) VALUES ('schema_version', '14')"))
        s.commit()
        migrate(s)
        assert get_schema_version(s) == CURRENT_SCHEMA_VERSION
        rows = s.exec(text("PRAGMA table_info(dismissed_inbox_items)")).all()
        cols = {r[1] for r in rows}
        assert cols == {"dismiss_key", "dismissed_at"}


def test_v15_migration_is_idempotent():
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as s:
        s.exec(text("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"))
        s.exec(text("INSERT INTO meta(key, value) VALUES ('schema_version', '14')"))
        s.commit()
        migrate(s)
        migrate(s)  # second run: must not raise
        assert get_schema_version(s) == CURRENT_SCHEMA_VERSION


def test_v15_table_exists_on_fresh_db():
    """Fresh DB path (current == 0) must end up with dismissed_inbox_items
    via SQLModel.metadata.create_all()."""
    from sqlmodel import SQLModel

    import net_alpha.db.tables  # noqa: F401 — ensure model registry is populated

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.exec(text("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"))
        s.commit()
        migrate(s)  # current == 0 path stamps version; table came from create_all
        assert get_schema_version(s) == CURRENT_SCHEMA_VERSION
        rows = s.exec(text("PRAGMA table_info(dismissed_inbox_items)")).all()
        cols = {r[1] for r in rows}
        assert cols == {"dismiss_key", "dismissed_at"}
