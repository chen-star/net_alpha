from sqlalchemy import create_engine, text
from sqlmodel import Session

from net_alpha.db.migrations import CURRENT_SCHEMA_VERSION, get_schema_version, migrate


def _bootstrap_v15(engine) -> None:
    """Create a fresh DB stamped at v15 (pre-migration baseline)."""
    with Session(engine) as s:
        s.exec(text("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)"))
        s.exec(text(
            "INSERT INTO meta(key, value) VALUES ('schema_version', '15')"
        ))
        s.exec(text(
            "CREATE TABLE position_targets ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  symbol TEXT NOT NULL UNIQUE,"
            "  target_amount NUMERIC NOT NULL,"
            "  target_unit TEXT NOT NULL,"
            "  created_at TEXT NOT NULL,"
            "  updated_at TEXT NOT NULL"
            ")"
        ))
        s.commit()


def test_v16_creates_position_target_tag_table():
    engine = create_engine("sqlite:///:memory:")
    _bootstrap_v15(engine)

    with Session(engine) as s:
        migrate(s)
        assert get_schema_version(s) == CURRENT_SCHEMA_VERSION
        assert CURRENT_SCHEMA_VERSION >= 16

        cols = list(s.exec(text("PRAGMA table_info(position_target_tag)")).all())
        col_names = {row[1] for row in cols}
        assert col_names == {"target_symbol", "tag"}

        idxs = list(s.exec(text(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='position_target_tag'"
        )).all())
        idx_names = {row[0] for row in idxs}
        assert "ix_position_target_tag_tag" in idx_names


def test_v16_is_idempotent():
    engine = create_engine("sqlite:///:memory:")
    _bootstrap_v15(engine)
    with Session(engine) as s:
        migrate(s)
    with Session(engine) as s:
        migrate(s)
        assert get_schema_version(s) == CURRENT_SCHEMA_VERSION


def test_v16_cascade_on_target_delete():
    engine = create_engine("sqlite:///:memory:")
    _bootstrap_v15(engine)
    with Session(engine) as s:
        migrate(s)
        s.exec(text("PRAGMA foreign_keys = ON"))
        s.exec(text(
            "INSERT INTO position_targets(symbol, target_amount, target_unit, created_at, updated_at) "
            "VALUES ('HIMS', 1000, 'usd', '2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        ))
        s.exec(text(
            "INSERT INTO position_target_tag(target_symbol, tag) VALUES ('HIMS', 'core')"
        ))
        s.commit()
        s.exec(text("DELETE FROM position_targets WHERE symbol='HIMS'"))
        s.commit()
        remaining = s.exec(text(
            "SELECT COUNT(*) FROM position_target_tag WHERE target_symbol='HIMS'"
        )).first()
        assert remaining[0] == 0
