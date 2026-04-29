"""Tests for migration from schema_version 1 → 2.

Synthesizes a v1-shape DB (no basis_source, no source, no realized_gl_lots),
then runs init_db() and verifies the new columns/table exist with safe defaults.
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy
from sqlmodel import create_engine

from net_alpha.db.connection import init_db


def _make_v1_db(path: Path) -> sqlalchemy.engine.Engine:
    """Create a SQLite DB with v1-shape schema and one trade + one violation row."""
    engine = create_engine(f"sqlite:///{path}", echo=False)
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("""
            CREATE TABLE accounts (
                id INTEGER PRIMARY KEY,
                broker TEXT NOT NULL,
                label TEXT NOT NULL,
                UNIQUE(broker, label)
            )
        """)
        )
        conn.execute(
            sqlalchemy.text("""
            CREATE TABLE imports (
                id INTEGER PRIMARY KEY,
                account_id INTEGER NOT NULL,
                csv_filename TEXT,
                csv_sha256 TEXT,
                imported_at TEXT,
                trade_count INTEGER
            )
        """)
        )
        conn.execute(
            sqlalchemy.text("""
            CREATE TABLE trades (
                id INTEGER PRIMARY KEY,
                import_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                natural_key TEXT NOT NULL,
                ticker TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                action TEXT NOT NULL,
                quantity REAL NOT NULL,
                proceeds REAL,
                cost_basis REAL,
                basis_unknown BOOLEAN DEFAULT 0,
                option_strike REAL,
                option_expiry TEXT,
                option_call_put TEXT
            )
        """)
        )
        conn.execute(
            sqlalchemy.text("""
            CREATE TABLE lots (
                id INTEGER PRIMARY KEY,
                trade_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                quantity REAL NOT NULL,
                cost_basis REAL NOT NULL,
                adjusted_basis REAL NOT NULL,
                option_strike REAL,
                option_expiry TEXT,
                option_call_put TEXT
            )
        """)
        )
        conn.execute(
            sqlalchemy.text("""
            CREATE TABLE wash_sale_violations (
                id INTEGER PRIMARY KEY,
                loss_trade_id INTEGER NOT NULL,
                replacement_trade_id INTEGER NOT NULL,
                loss_account_id INTEGER NOT NULL,
                buy_account_id INTEGER NOT NULL,
                loss_sale_date TEXT NOT NULL,
                triggering_buy_date TEXT NOT NULL,
                ticker TEXT NOT NULL DEFAULT '',
                confidence TEXT NOT NULL,
                disallowed_loss REAL NOT NULL,
                matched_quantity REAL NOT NULL
            )
        """)
        )
        conn.execute(
            sqlalchemy.text("""
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)
        """)
        )
        conn.execute(sqlalchemy.text("INSERT INTO accounts(id, broker, label) VALUES (1, 'schwab', 'personal')"))
        conn.execute(
            sqlalchemy.text(
                "INSERT INTO imports(id, account_id, csv_filename, csv_sha256, imported_at, trade_count) "
                "VALUES (1, 1, 'x.csv', 'abc', '2026-01-01T00:00:00', 1)"
            )
        )
        conn.execute(
            sqlalchemy.text(
                "INSERT INTO trades(id, import_id, account_id, natural_key, ticker, trade_date, action, quantity) "
                "VALUES (1, 1, 1, 'k1', 'AAPL', '2026-01-02', 'Buy', 1.0)"
            )
        )
        conn.execute(
            sqlalchemy.text(
                "INSERT INTO wash_sale_violations(id, loss_trade_id, replacement_trade_id, loss_account_id, "
                "buy_account_id, loss_sale_date, triggering_buy_date, confidence, disallowed_loss, matched_quantity) "
                "VALUES (1, 1, 1, 1, 1, '2026-01-02', '2026-01-03', 'Confirmed', 100.0, 1.0)"
            )
        )
        conn.execute(sqlalchemy.text("INSERT INTO meta(key, value) VALUES ('schema_version', '1')"))
    return engine


def test_init_db_migrates_v1_to_v2_adds_basis_source(tmp_path):
    db_path = tmp_path / "v1.db"
    _make_v1_db(db_path)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    init_db(engine)
    with engine.connect() as conn:
        cols = [r[1] for r in conn.execute(sqlalchemy.text("PRAGMA table_info(trades)")).all()]
    assert "basis_source" in cols


def test_init_db_migrates_v1_to_v2_adds_violation_source(tmp_path):
    db_path = tmp_path / "v1.db"
    _make_v1_db(db_path)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    init_db(engine)
    with engine.connect() as conn:
        cols = [r[1] for r in conn.execute(sqlalchemy.text("PRAGMA table_info(wash_sale_violations)")).all()]
    assert "source" in cols


def test_init_db_migrates_v1_to_v2_creates_realized_gl_lots(tmp_path):
    db_path = tmp_path / "v1.db"
    _make_v1_db(db_path)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    init_db(engine)
    with engine.connect() as conn:
        tables = [
            r[0] for r in conn.execute(sqlalchemy.text("SELECT name FROM sqlite_master WHERE type='table'")).all()
        ]
    assert "realized_gl_lots" in tables


def test_init_db_preserves_existing_rows_with_default_basis_source(tmp_path):
    db_path = tmp_path / "v1.db"
    _make_v1_db(db_path)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    init_db(engine)
    with engine.connect() as conn:
        row = conn.execute(sqlalchemy.text("SELECT id, basis_source FROM trades WHERE id=1")).first()
    assert row is not None
    assert row[1] == "unknown"


def test_init_db_preserves_existing_violation_with_default_source(tmp_path):
    db_path = tmp_path / "v1.db"
    _make_v1_db(db_path)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    init_db(engine)
    with engine.connect() as conn:
        row = conn.execute(sqlalchemy.text("SELECT id, source FROM wash_sale_violations WHERE id=1")).first()
    assert row is not None
    assert row[1] == "engine"


def test_init_db_bumps_schema_version_to_2(tmp_path):
    db_path = tmp_path / "v1.db"
    _make_v1_db(db_path)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    init_db(engine)
    with engine.connect() as conn:
        v = conn.execute(sqlalchemy.text("SELECT value FROM meta WHERE key='schema_version'")).scalar()
    # v1 DBs are migrated through every step up to CURRENT_SCHEMA_VERSION (11).
    assert v == "11"


def test_init_db_on_fresh_db_creates_v2_directly(tmp_path):
    """Fresh DB (no tables) should create current schema and set schema_version=CURRENT."""
    db_path = tmp_path / "fresh.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    init_db(engine)
    with engine.connect() as conn:
        v = conn.execute(sqlalchemy.text("SELECT value FROM meta WHERE key='schema_version'")).scalar()
        cols = [r[1] for r in conn.execute(sqlalchemy.text("PRAGMA table_info(trades)")).all()]
        tables = [
            r[0] for r in conn.execute(sqlalchemy.text("SELECT name FROM sqlite_master WHERE type='table'")).all()
        ]
    assert v == "11"
    assert "basis_source" in cols
    assert "transfer_date" in cols
    assert "transfer_group_id" in cols
    assert "is_section_1256" in cols
    assert "realized_gl_lots" in tables
    assert "exempt_matches" in tables
    assert "section_1256_classifications" in tables
