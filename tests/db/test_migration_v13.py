"""v12 → v13: add user_preferences.theme column with default 'system'."""

from sqlalchemy import create_engine, text
from sqlmodel import Session, SQLModel

import net_alpha.db.tables as _tables  # noqa: F401 — registers all SQLModel table classes
from net_alpha.db.migrations import migrate


def _v12_engine():
    """In-memory engine seeded at v12 with a user_preferences row that lacks the theme column."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.exec(text("DROP TABLE IF EXISTS user_preferences"))
        # Recreate without theme (the v9 shape) so v13 has work to do.
        session.exec(
            text(
                "CREATE TABLE user_preferences ("
                "account_id INTEGER PRIMARY KEY, "
                "profile TEXT NOT NULL DEFAULT 'active', "
                "density TEXT NOT NULL DEFAULT 'comfortable', "
                "updated_at TEXT NOT NULL)"
            )
        )
        # Seed an account + a row representing a user upgrading without an explicit theme choice.
        session.exec(
            text(
                "INSERT INTO accounts(broker, label) VALUES ('schwab', 'XXX180')"
                if not session.exec(text("SELECT id FROM accounts LIMIT 1")).first()
                else "SELECT 1"
            )
        )
        aid_row = session.exec(text("SELECT id FROM accounts LIMIT 1")).first()
        aid = aid_row[0]
        session.exec(
            text(
                "INSERT INTO user_preferences(account_id, profile, density, updated_at) "
                "VALUES (:aid, 'active', 'comfortable', '2024-01-01T00:00:00Z')"
            ).bindparams(aid=aid)
        )
        session.exec(text("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', '12')"))
        session.commit()
    return engine


def test_v13_adds_theme_column():
    engine = _v12_engine()
    with Session(engine) as s:
        migrate(s)
        cols = {r[1] for r in s.exec(text("PRAGMA table_info(user_preferences)")).all()}
        assert "theme" in cols


def test_v13_existing_rows_default_to_system():
    """Pre-existing rows must read back theme='system' so behaviour is unchanged on upgrade."""
    engine = _v12_engine()
    with Session(engine) as s:
        migrate(s)
        row = s.exec(text("SELECT theme FROM user_preferences LIMIT 1")).first()
        assert row is not None
        assert row[0] == "system"


def test_v13_idempotent():
    """Running migrate twice must not raise (the ALTER TABLE is guarded by _column_exists)."""
    engine = _v12_engine()
    with Session(engine) as s:
        migrate(s)
    with Session(engine) as s:
        migrate(s)  # second run on already-migrated DB
    with Session(engine) as s:
        cols = {r[1] for r in s.exec(text("PRAGMA table_info(user_preferences)")).all()}
        assert "theme" in cols


def test_v13_bumps_schema_version():
    engine = _v12_engine()
    with Session(engine) as s:
        migrate(s)
        v = s.exec(text("SELECT value FROM meta WHERE key='schema_version'")).first()
        assert v is not None
        # migrate() carries past v13; the only requirement here is that v13 ran.
        assert int(v[0]) >= 13
