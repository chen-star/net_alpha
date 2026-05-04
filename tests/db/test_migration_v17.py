from sqlalchemy import create_engine, text
from sqlmodel import Session

from net_alpha.db.migrations import CURRENT_SCHEMA_VERSION, get_schema_version, migrate


def _bootstrap_v16(engine) -> None:
    """Create a fresh DB stamped at v16 (pre-migration baseline)."""
    with Session(engine) as s:
        s.exec(text("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)"))
        s.exec(text(
            "INSERT INTO meta(key, value) VALUES ('schema_version', '16')"
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
        s.exec(text(
            "CREATE TABLE position_target_tag ("
            "  target_symbol TEXT NOT NULL,"
            "  tag           TEXT NOT NULL,"
            "  PRIMARY KEY (target_symbol, tag)"
            ")"
        ))
        # Two existing targets in non-alpha insertion order. The migration
        # should backfill sort_order by alpha rank, not insertion order.
        s.exec(text(
            "INSERT INTO position_targets(symbol, target_amount, target_unit, created_at, updated_at) "
            "VALUES ('VOO', 1000, 'usd', '2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        ))
        s.exec(text(
            "INSERT INTO position_targets(symbol, target_amount, target_unit, created_at, updated_at) "
            "VALUES ('AAPL', 500, 'usd', '2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        ))
        s.commit()


def test_v17_adds_sort_order_column():
    engine = create_engine("sqlite:///:memory:")
    _bootstrap_v16(engine)

    with Session(engine) as s:
        migrate(s)
        assert get_schema_version(s) == CURRENT_SCHEMA_VERSION
        assert CURRENT_SCHEMA_VERSION >= 17

        cols = list(s.exec(text("PRAGMA table_info(position_targets)")).all())
        col_by_name = {row[1]: row for row in cols}
        assert "sort_order" in col_by_name
        # PRAGMA table_info row layout: (cid, name, type, notnull, dflt_value, pk)
        assert col_by_name["sort_order"][3] == 1  # NOT NULL
        # Default value column may be a quoted string in SQLite; compare loosely.
        assert str(col_by_name["sort_order"][4]).strip("'\"") == "0"


def test_v17_backfills_alpha_rank():
    engine = create_engine("sqlite:///:memory:")
    _bootstrap_v16(engine)

    with Session(engine) as s:
        migrate(s)
        rows = list(s.exec(text(
            "SELECT symbol, sort_order FROM position_targets ORDER BY symbol"
        )).all())
        assert rows == [("AAPL", 1), ("VOO", 2)]


def test_v17_is_idempotent():
    engine = create_engine("sqlite:///:memory:")
    _bootstrap_v16(engine)
    with Session(engine) as s:
        migrate(s)
    with Session(engine) as s:
        migrate(s)
        assert get_schema_version(s) == CURRENT_SCHEMA_VERSION
        # Second run must NOT re-backfill (would clobber any user reorder).
        # Insert a row, manually set its sort_order to 99, run migrate again,
        # and confirm 99 is preserved.
    with Session(engine) as s:
        s.exec(text(
            "INSERT INTO position_targets(symbol, target_amount, target_unit, created_at, updated_at, sort_order) "
            "VALUES ('MSFT', 100, 'usd', '2026-01-01T00:00:00', '2026-01-01T00:00:00', 99)"
        ))
        s.commit()
    with Session(engine) as s:
        migrate(s)
        row = s.exec(text("SELECT sort_order FROM position_targets WHERE symbol='MSFT'")).first()
        assert row[0] == 99
