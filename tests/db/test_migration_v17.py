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


def test_v17_migrate_is_noop_on_already_migrated_db():
    """Running migrate twice in a row leaves the schema unchanged and
    does not modify existing sort_order values."""
    engine = create_engine("sqlite:///:memory:")
    _bootstrap_v16(engine)
    with Session(engine) as s:
        migrate(s)
    # Snapshot what the migration produced.
    with Session(engine) as s:
        before = list(s.exec(text(
            "SELECT symbol, sort_order FROM position_targets ORDER BY symbol"
        )).all())
    # Run again — must not change anything.
    with Session(engine) as s:
        migrate(s)
        assert get_schema_version(s) == CURRENT_SCHEMA_VERSION
        after = list(s.exec(text(
            "SELECT symbol, sort_order FROM position_targets ORDER BY symbol"
        )).all())
    assert after == before


def test_v17_does_not_clobber_user_sort_order():
    """A re-run of the migration on a DB that already has v17 must NOT
    overwrite a user-edited sort_order with the alpha-rank backfill."""
    engine = create_engine("sqlite:///:memory:")
    _bootstrap_v16(engine)
    with Session(engine) as s:
        migrate(s)
    # Insert a row and manually pin its sort_order to 99 (simulating a
    # user-edited order via set_target_order).
    with Session(engine) as s:
        s.exec(text(
            "INSERT INTO position_targets(symbol, target_amount, target_unit, created_at, updated_at, sort_order) "
            "VALUES ('MSFT', 100, 'usd', '2026-01-01T00:00:00', '2026-01-01T00:00:00', 99)"
        ))
        s.commit()
    # Run migrate again — the user-set 99 must be preserved.
    with Session(engine) as s:
        migrate(s)
        row = s.exec(text(
            "SELECT sort_order FROM position_targets WHERE symbol='MSFT'"
        )).first()
        assert row[0] == 99
