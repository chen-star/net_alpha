"""v21 → v22: lots.tacked_acquired_date for IRC §1223(4) holding-period tacking."""

from sqlmodel import Session, create_engine, text

from net_alpha.db.migrations import (
    CURRENT_SCHEMA_VERSION,
    _migrate_v21_to_v22,
    set_schema_version,
)


def test_current_schema_version_is_24():
    assert CURRENT_SCHEMA_VERSION == 24


def test_v21_to_v22_adds_column_idempotently():
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as s:
        s.exec(text("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)"))
        # Minimal lots table the migration expects.
        s.exec(
            text(
                "CREATE TABLE lots ("
                "id INTEGER PRIMARY KEY, trade_id INTEGER, account_id INTEGER, "
                "ticker TEXT, trade_date TEXT, quantity REAL, "
                "cost_basis REAL, adjusted_basis REAL)"
            )
        )
        set_schema_version(s, 21)

        _migrate_v21_to_v22(s)
        s.commit()

        cols = {r[1] for r in s.exec(text("PRAGMA table_info(lots)")).all()}
        assert "tacked_acquired_date" in cols

        # Idempotent — running it again must not raise.
        _migrate_v21_to_v22(s)
        s.commit()


def test_v21_to_v22_no_op_when_lots_missing():
    """Migration must not crash on a DB that has no lots table yet."""
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as s:
        s.exec(text("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)"))
        set_schema_version(s, 21)
        _migrate_v21_to_v22(s)  # must not raise
        s.commit()
