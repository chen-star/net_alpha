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
  v8 — Adds cash_events table; trades.gross_cash_impact; imports.cash_event_count.
  v9 — Adds user_preferences (per-account profile + density).
  v10 — Adds trades.transfer_date and trades.transfer_group_id so transfer
        rows can preserve the original broker-statement date alongside an
        edited acquisition date, and a single transfer can be split into
        multiple sibling rows that share a group id.
  v11 — Adds §1256 awareness: trades.is_section_1256 column,
        exempt_matches table, section_1256_classifications table,
        and stamps the universe-hash + engine-version meta rows.
  v12 — Adds position_targets and historical_price_cache tables.
  v13 — Adds user_preferences.theme column ('system' | 'light' | 'dark',
        default 'system') for the light/dark mode toggle.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlmodel import Session

CURRENT_SCHEMA_VERSION = 13


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


def _migrate_v7_to_v8(session: Session) -> None:
    """Add cash_events table; gross_cash_impact column on trades; cash_event_count
    on imports. All idempotent so re-running on a partially-migrated DB is safe.
    """
    if not _table_exists(session, "cash_events"):
        session.exec(
            text(
                "CREATE TABLE cash_events ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "import_id INTEGER NOT NULL REFERENCES imports(id), "
                "account_id INTEGER NOT NULL REFERENCES accounts(id), "
                "natural_key TEXT NOT NULL, "
                "event_date TEXT NOT NULL, "
                "kind TEXT NOT NULL, "
                "amount REAL NOT NULL, "
                "ticker TEXT, "
                "description TEXT NOT NULL DEFAULT '', "
                "CONSTRAINT uq_cash_event_account_natkey UNIQUE (account_id, natural_key))"
            )
        )
        session.exec(text("CREATE INDEX ix_cash_events_account_id ON cash_events(account_id)"))
        session.exec(text("CREATE INDEX ix_cash_events_import_id ON cash_events(import_id)"))
        session.exec(text("CREATE INDEX ix_cash_events_event_date ON cash_events(event_date)"))
        session.exec(text("CREATE INDEX ix_cash_events_natural_key ON cash_events(natural_key)"))
        session.exec(text("CREATE INDEX ix_cash_events_ticker ON cash_events(ticker)"))
    if _table_exists(session, "trades") and not _column_exists(session, "trades", "gross_cash_impact"):
        session.exec(text("ALTER TABLE trades ADD COLUMN gross_cash_impact REAL"))
    if _table_exists(session, "imports") and not _column_exists(session, "imports", "cash_event_count"):
        session.exec(text("ALTER TABLE imports ADD COLUMN cash_event_count INTEGER DEFAULT 0"))
    session.commit()


def _migrate_v8_to_v9(session: Session) -> None:
    """Add user_preferences (per-account profile + density). Idempotent."""
    if not _table_exists(session, "user_preferences"):
        session.exec(
            text(
                "CREATE TABLE user_preferences ("
                "account_id INTEGER PRIMARY KEY, "
                "profile TEXT NOT NULL DEFAULT 'active', "
                "density TEXT NOT NULL DEFAULT 'comfortable', "
                "updated_at TEXT NOT NULL, "
                "FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE)"
            )
        )
    session.commit()


def _migrate_v9_to_v10(session: Session) -> None:
    """Add trades.transfer_date and trades.transfer_group_id. Idempotent."""
    if not _table_exists(session, "trades"):
        return
    if not _column_exists(session, "trades", "transfer_date"):
        session.exec(text("ALTER TABLE trades ADD COLUMN transfer_date TEXT"))
    if not _column_exists(session, "trades", "transfer_group_id"):
        session.exec(text("ALTER TABLE trades ADD COLUMN transfer_group_id TEXT"))
        session.exec(text("CREATE INDEX IF NOT EXISTS ix_trades_transfer_group_id ON trades(transfer_group_id)"))
    session.commit()


def _stamp_section_1256_meta(session: Session) -> None:
    """Stamp universe hash + engine version. Idempotent. Called by both
    the fresh-DB branch of migrate() and _migrate_v10_to_v11."""
    from net_alpha.section_1256.universe import universe_hash

    session.exec(
        text(
            "INSERT INTO meta(key, value) VALUES ('section_1256_universe_hash', :v) "
            "ON CONFLICT(key) DO UPDATE SET value=:v"
        ).bindparams(v=universe_hash())
    )
    session.exec(
        text(
            "INSERT INTO meta(key, value) VALUES ('wash_sale_engine_version', :v) "
            "ON CONFLICT(key) DO UPDATE SET value=:v"
        ).bindparams(v=str(CURRENT_SCHEMA_VERSION))
    )


def _migrate_v10_to_v11(session: Session) -> None:
    """Add §1256 awareness: trades.is_section_1256 column,
    exempt_matches table, section_1256_classifications table,
    and stamp the universe-hash + engine-version meta rows.
    Idempotent.
    """
    # 1. Add column on trades (no-op if preflight in migrate() already added it)
    if _table_exists(session, "trades") and not _column_exists(session, "trades", "is_section_1256"):
        session.exec(text("ALTER TABLE trades ADD COLUMN is_section_1256 INTEGER NOT NULL DEFAULT 0"))

    # 2. Create exempt_matches (FK columns are INTEGER to match trades.id)
    if not _table_exists(session, "exempt_matches"):
        session.exec(
            text("""
            CREATE TABLE exempt_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loss_trade_id INTEGER NOT NULL,
                triggering_buy_id INTEGER NOT NULL,
                exempt_reason TEXT NOT NULL,
                rule_citation TEXT NOT NULL,
                notional_disallowed NUMERIC NOT NULL,
                confidence TEXT NOT NULL,
                matched_quantity REAL NOT NULL,
                loss_account TEXT NOT NULL,
                buy_account TEXT NOT NULL,
                loss_sale_date TEXT NOT NULL,
                triggering_buy_date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (loss_trade_id) REFERENCES trades(id),
                FOREIGN KEY (triggering_buy_id) REFERENCES trades(id)
            )
        """)
        )
        session.exec(text("CREATE INDEX IF NOT EXISTS ix_exempt_matches_loss_trade ON exempt_matches(loss_trade_id)"))
        session.exec(
            text("CREATE INDEX IF NOT EXISTS ix_exempt_matches_triggering_buy ON exempt_matches(triggering_buy_id)")
        )
        session.exec(text("CREATE INDEX IF NOT EXISTS ix_exempt_matches_ticker ON exempt_matches(ticker)"))
        session.exec(
            text("CREATE INDEX IF NOT EXISTS ix_exempt_matches_loss_sale_date ON exempt_matches(loss_sale_date)")
        )

    # 3. Create section_1256_classifications
    if not _table_exists(session, "section_1256_classifications"):
        session.exec(
            text("""
            CREATE TABLE section_1256_classifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id INTEGER NOT NULL UNIQUE,
                realized_pnl NUMERIC NOT NULL,
                long_term_portion NUMERIC NOT NULL,
                short_term_portion NUMERIC NOT NULL,
                underlying TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (trade_id) REFERENCES trades(id)
            )
        """)
        )
        session.exec(
            text(
                "CREATE INDEX IF NOT EXISTS ix_s1256_classifications_underlying"
                " ON section_1256_classifications(underlying)"
            )
        )

    # 4. Stamp universe hash + engine version
    _stamp_section_1256_meta(session)

    session.commit()


def _migrate_v11_to_v12(session: Session) -> None:
    """Add position_targets (user-managed per-symbol target $ or share counts)
    and historical_price_cache (read-through cache for benchmark closes).
    Idempotent.
    """
    if not _table_exists(session, "position_targets"):
        session.exec(
            text("""
            CREATE TABLE position_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                target_amount NUMERIC NOT NULL,
                target_unit TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(symbol)
            )
            """)
        )
        session.exec(text("CREATE INDEX IF NOT EXISTS ix_position_targets_symbol ON position_targets(symbol)"))

    if not _table_exists(session, "historical_price_cache"):
        session.exec(
            text("""
            CREATE TABLE historical_price_cache (
                symbol TEXT NOT NULL,
                on_date TEXT NOT NULL,
                close_price NUMERIC,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY(symbol, on_date)
            )
            """)
        )
    session.commit()


def _migrate_v12_to_v13(session: Session) -> None:
    """Add user_preferences.theme column. Idempotent.

    Existing rows get 'system' (follow OS preference) so behavior is unchanged
    for users upgrading without explicitly picking a theme.
    """
    if _table_exists(session, "user_preferences") and not _column_exists(session, "user_preferences", "theme"):
        session.exec(text("ALTER TABLE user_preferences ADD COLUMN theme TEXT NOT NULL DEFAULT 'system'"))
    session.commit()


def migrate(session: Session) -> None:
    """Apply pending migrations idempotently."""
    # PREFLIGHT: ensure latest TradeRow columns exist before per-version steps
    # (SQLModel ORM SELECTs in older migration steps include all current columns)
    if _table_exists(session, "trades") and not _column_exists(session, "trades", "is_section_1256"):
        session.exec(text("ALTER TABLE trades ADD COLUMN is_section_1256 INTEGER NOT NULL DEFAULT 0"))
        session.commit()

    current = get_schema_version(session)
    if current == 0:
        # Fresh DB: SQLModel.metadata.create_all has already produced the
        # current-shape tables. Just stamp the version and meta rows.
        set_schema_version(session, CURRENT_SCHEMA_VERSION)
        _stamp_section_1256_meta(session)
        session.commit()
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
        current = 7
    if current < 8:
        _migrate_v7_to_v8(session)
        set_schema_version(session, 8)
        current = 8
    if current < 9:
        _migrate_v8_to_v9(session)
        set_schema_version(session, 9)
        current = 9
    if current < 10:
        _migrate_v9_to_v10(session)
        set_schema_version(session, 10)
        current = 10
    if current < 11:
        _migrate_v10_to_v11(session)
        set_schema_version(session, 11)
        current = 11
    if current < 12:
        _migrate_v11_to_v12(session)
        set_schema_version(session, 12)
        current = 12
    if current < 13:
        _migrate_v12_to_v13(session)
        set_schema_version(session, 13)
        return
    if current > CURRENT_SCHEMA_VERSION:
        raise RuntimeError(
            f"DB schema_version={current} is newer than this binary "
            f"(supports {CURRENT_SCHEMA_VERSION}). Upgrade net-alpha."
        )
