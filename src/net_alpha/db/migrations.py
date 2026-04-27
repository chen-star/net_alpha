"""Hand-written migrations.

Schema versions:
  v1 — Initial v2.x schema (TradeRow, LotRow, WashSaleViolationRow, etc.)
  v2 — Adds RealizedGLLotRow table; adds Trade.basis_source, WashSaleViolation.source columns.
  v3 — Adds PriceCacheRow table for the pricing subsystem.
  v4 — Adds aggregate columns to imports (date range, type counts, parse warnings).
  v5 — Adds imports.duplicate_trades count so re-imports show "X dupes" instead of "no records".
  v6 — Adds trades.is_manual and trades.transfer_basis_user_set; relaxes trades.import_id NOT NULL.
  v7 — Adds splits and lot_overrides tables for stock-split handling and
       manual lot edits.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlmodel import Session

CURRENT_SCHEMA_VERSION = 7


def get_schema_version(session: Session) -> int:
    row = session.exec(text("SELECT value FROM meta WHERE key='schema_version'")).first()
    return int(row[0]) if row else 0


def set_schema_version(session: Session, version: int) -> None:
    session.exec(
        text("INSERT INTO meta(key, value) VALUES ('schema_version', :v) ON CONFLICT(key) DO UPDATE SET value=:v"),
        params={"v": str(version)},
    )
    session.commit()


def _column_exists(session: Session, table: str, column: str) -> bool:
    rows = session.exec(text(f"PRAGMA table_info({table})")).all()
    return any(r[1] == column for r in rows)


def _table_exists(session: Session, table: str) -> bool:
    row = session.exec(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        params={"n": table},
    ).first()
    return row is not None


def _migrate_v1_to_v2(session: Session) -> None:
    if _table_exists(session, "trades") and not _column_exists(session, "trades", "basis_source"):
        session.exec(text("ALTER TABLE trades ADD COLUMN basis_source TEXT NOT NULL DEFAULT 'unknown'"))
    if _table_exists(session, "wash_sale_violations") and not _column_exists(session, "wash_sale_violations", "source"):
        session.exec(text("ALTER TABLE wash_sale_violations ADD COLUMN source TEXT NOT NULL DEFAULT 'engine'"))
    # realized_gl_lots is created by SQLModel.metadata.create_all in init_db.
    session.commit()


def _migrate_v2_to_v3(session: Session) -> None:
    # On a fresh DB, SQLModel.metadata.create_all already created price_cache.
    # On an upgrade from v2, create_all was not re-run, so we create it here.
    if not _table_exists(session, "price_cache"):
        session.exec(
            text(
                "CREATE TABLE price_cache ("
                "symbol TEXT PRIMARY KEY, "
                "price REAL NOT NULL, "
                "as_of TEXT NOT NULL, "
                "fetched_at TEXT NOT NULL, "
                "source TEXT NOT NULL)"
            )
        )
        session.commit()


def _migrate_v3_to_v4(session: Session) -> None:
    """Add 6 nullable aggregate columns to imports. Backfill happens later via
    `import_.backfill.backfill_import_aggregates`, called from init_db."""
    additions = [
        ("min_trade_date", "TEXT"),
        ("max_trade_date", "TEXT"),
        ("equity_count", "INTEGER"),
        ("option_count", "INTEGER"),
        ("option_expiry_count", "INTEGER"),
        ("parse_warnings_json", "TEXT"),
    ]
    for col, sqltype in additions:
        if not _column_exists(session, "imports", col):
            session.exec(text(f"ALTER TABLE imports ADD COLUMN {col} {sqltype}"))
    session.commit()


def _migrate_v4_to_v5(session: Session) -> None:
    """Add imports.duplicate_trades. Default 0 for existing rows so the imports
    summary cell renders "no records" for old re-imports rather than misleading
    text like "skipped 0 duplicates"."""
    if _table_exists(session, "imports") and not _column_exists(session, "imports", "duplicate_trades"):
        session.exec(text("ALTER TABLE imports ADD COLUMN duplicate_trades INTEGER NOT NULL DEFAULT 0"))
    session.commit()


def _migrate_v5_to_v6(session: Session) -> None:
    if not _table_exists(session, "trades"):
        return
    if not _column_exists(session, "trades", "is_manual"):
        session.exec(text("ALTER TABLE trades ADD COLUMN is_manual INTEGER NOT NULL DEFAULT 0"))
    if not _column_exists(session, "trades", "transfer_basis_user_set"):
        session.exec(text("ALTER TABLE trades ADD COLUMN transfer_basis_user_set INTEGER NOT NULL DEFAULT 0"))
    # Relax import_id NOT NULL via SQLite rebuild dance.
    info = session.exec(text("PRAGMA table_info(trades)")).all()
    import_id_row = next((r for r in info if r[1] == "import_id"), None)
    if import_id_row is not None and import_id_row[3] == 1:  # notnull flag is column 3
        session.exec(text("PRAGMA foreign_keys=OFF"))
        session.exec(
            text("""
            CREATE TABLE trades_new (
              id INTEGER PRIMARY KEY,
              import_id INTEGER NULL REFERENCES imports(id),
              account_id INTEGER NOT NULL REFERENCES accounts(id),
              natural_key TEXT NOT NULL,
              ticker TEXT NOT NULL,
              trade_date TEXT NOT NULL,
              action TEXT NOT NULL,
              quantity FLOAT NOT NULL,
              proceeds FLOAT,
              cost_basis FLOAT,
              basis_unknown INTEGER NOT NULL DEFAULT 0,
              option_strike FLOAT,
              option_expiry TEXT,
              option_call_put TEXT,
              basis_source TEXT NOT NULL DEFAULT 'unknown',
              is_manual INTEGER NOT NULL DEFAULT 0,
              transfer_basis_user_set INTEGER NOT NULL DEFAULT 0,
              CONSTRAINT uq_trade_account_natkey UNIQUE (account_id, natural_key)
            )
        """)
        )
        session.exec(
            text("""
            INSERT INTO trades_new
            SELECT id, import_id, account_id, natural_key, ticker, trade_date, action,
                   quantity, proceeds, cost_basis, basis_unknown,
                   option_strike, option_expiry, option_call_put,
                   basis_source, is_manual, transfer_basis_user_set
            FROM trades
        """)
        )
        session.exec(text("DROP TABLE trades"))
        session.exec(text("ALTER TABLE trades_new RENAME TO trades"))
        session.exec(text("CREATE INDEX ix_trades_account_id ON trades(account_id)"))
        session.exec(text("CREATE INDEX ix_trades_import_id ON trades(import_id)"))
        session.exec(text("CREATE INDEX ix_trades_natural_key ON trades(natural_key)"))
        session.exec(text("CREATE INDEX ix_trades_ticker ON trades(ticker)"))
        session.exec(text("CREATE INDEX ix_trades_trade_date ON trades(trade_date)"))
        session.exec(text("PRAGMA foreign_keys=ON"))
    session.commit()


def _migrate_v6_to_v7(session: Session) -> None:
    if not _table_exists(session, "splits"):
        session.exec(
            text(
                "CREATE TABLE splits ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "symbol TEXT NOT NULL, "
                "split_date TEXT NOT NULL, "
                "ratio REAL NOT NULL, "
                "source TEXT NOT NULL, "
                "fetched_at TEXT NOT NULL, "
                "CONSTRAINT uq_splits_symbol_date UNIQUE (symbol, split_date))"
            )
        )
        session.exec(text("CREATE INDEX ix_splits_symbol ON splits(symbol)"))
    if not _table_exists(session, "lot_overrides"):
        session.exec(
            text(
                "CREATE TABLE lot_overrides ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "trade_id INTEGER NOT NULL REFERENCES trades(id), "
                "field TEXT NOT NULL, "
                "old_value REAL NOT NULL, "
                "new_value REAL NOT NULL, "
                "reason TEXT NOT NULL, "
                "edited_at TEXT NOT NULL, "
                "split_id INTEGER NULL REFERENCES splits(id))"
            )
        )
        session.exec(text("CREATE INDEX ix_lot_overrides_trade_id ON lot_overrides(trade_id)"))
        session.exec(text("CREATE INDEX ix_lot_overrides_split_id ON lot_overrides(split_id)"))
    session.commit()


def migrate(session: Session) -> None:
    """Apply pending migrations idempotently."""
    current = get_schema_version(session)
    if current == 0:
        # Fresh DB: SQLModel.metadata.create_all has already produced the
        # current-shape tables. Just stamp the version.
        set_schema_version(session, CURRENT_SCHEMA_VERSION)
        return
    if current == 1:
        _migrate_v1_to_v2(session)
        set_schema_version(session, 2)
        current = 2
    if current == 2:
        _migrate_v2_to_v3(session)
        set_schema_version(session, 3)
        current = 3
    if current == 3:
        _migrate_v3_to_v4(session)
        set_schema_version(session, 4)
        current = 4
    if current == 4:
        _migrate_v4_to_v5(session)
        set_schema_version(session, 5)
        current = 5
    if current < 6:
        _migrate_v5_to_v6(session)
        set_schema_version(session, 6)
        current = 6
    if current < 7:
        _migrate_v6_to_v7(session)
        set_schema_version(session, 7)
        return
    if current > CURRENT_SCHEMA_VERSION:
        raise RuntimeError(
            f"DB schema_version={current} is newer than this binary "
            f"(supports {CURRENT_SCHEMA_VERSION}). Upgrade net-alpha."
        )
