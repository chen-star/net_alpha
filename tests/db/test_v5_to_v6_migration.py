from __future__ import annotations

from sqlalchemy import text
from sqlmodel import Session

from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.migrations import (
    CURRENT_SCHEMA_VERSION,
    _column_exists,
    get_schema_version,
    migrate,
    set_schema_version,
)


def _force_v5(session: Session) -> None:
    """Pretend the DB is v5: drop the new v6 columns if present, set version."""
    set_schema_version(session, 5)


def test_v5_to_v6_adds_new_columns(tmp_path):
    """Test that migrating from v5 adds is_manual and transfer_basis_user_set columns.

    TradeRow now includes is_manual and transfer_basis_user_set (Task 2 complete),
    so init_db creates a fresh DB that already has the v6 columns. We simulate the
    v5 → v6 migration path by creating a v5-style DB manually (without those columns),
    stamping it as v5, and then running migrate() to verify the columns are added.
    """
    db_path = tmp_path / "db.sqlite"
    engine = get_engine(db_path)
    # Build a v5-style schema manually without the new columns
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)"))
        conn.execute(
            text(
                "CREATE TABLE accounts (id INTEGER PRIMARY KEY, broker TEXT NOT NULL, label TEXT NOT NULL, "
                "UNIQUE (broker, label))"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE imports (id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, "
                "csv_filename TEXT NOT NULL, csv_sha256 TEXT NOT NULL, imported_at TEXT NOT NULL, "
                "trade_count INTEGER NOT NULL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE trades (id INTEGER PRIMARY KEY, import_id INTEGER NOT NULL, "
                "account_id INTEGER NOT NULL, natural_key TEXT NOT NULL, ticker TEXT NOT NULL, "
                "trade_date TEXT NOT NULL, action TEXT NOT NULL, quantity REAL NOT NULL, "
                "proceeds REAL, cost_basis REAL, basis_unknown INTEGER NOT NULL DEFAULT 0, "
                "option_strike REAL, option_expiry TEXT, option_call_put TEXT, "
                "basis_source TEXT NOT NULL DEFAULT 'unknown', "
                "UNIQUE (account_id, natural_key))"
            )
        )
        conn.execute(text("INSERT INTO meta(key, value) VALUES ('schema_version', '5')"))
    with Session(engine) as s:
        assert not _column_exists(s, "trades", "is_manual")
        assert not _column_exists(s, "trades", "transfer_basis_user_set")
        assert get_schema_version(s) == 5
        migrate(s)
        assert get_schema_version(s) == CURRENT_SCHEMA_VERSION
        assert _column_exists(s, "trades", "is_manual")
        assert _column_exists(s, "trades", "transfer_basis_user_set")


def test_v5_to_v6_relaxes_import_id_not_null(tmp_path):
    """After migration, inserting a trade with import_id=NULL must succeed."""
    db_path = tmp_path / "db.sqlite"
    engine = get_engine(db_path)
    init_db(engine)
    with Session(engine) as s:
        # Stamp v5 so migrate() will run the v5→v6 step (which includes the rebuild dance)
        _force_v5(s)
        s.commit()
    with Session(engine) as s:
        migrate(s)
    with Session(engine) as s:
        s.exec(text("INSERT INTO accounts(broker, label) VALUES ('Schwab','Tax')"))
        s.commit()
    with Session(engine) as s:
        s.exec(
            text(
                "INSERT INTO trades(import_id, account_id, natural_key, ticker, trade_date, "
                "action, quantity, basis_source, basis_unknown, is_manual, transfer_basis_user_set) "
                "VALUES (NULL, 1, 'manual:abc', 'AAPL', '2026-01-15', 'Buy', 10, 'user', 0, 1, 0)"
            )
        )
        s.commit()
        row = s.exec(text("SELECT id, import_id, is_manual FROM trades WHERE natural_key='manual:abc'")).first()
        assert row is not None
        assert row[1] is None
        assert row[2] == 1
