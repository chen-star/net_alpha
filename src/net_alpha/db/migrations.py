"""Hand-written migrations.

Schema versions:
  v1 — Initial v2.x schema (TradeRow, LotRow, WashSaleViolationRow, etc.)
  v2 — Adds RealizedGLLotRow table; adds Trade.basis_source, WashSaleViolation.source columns.
  v3 — Adds PriceCacheRow table for the pricing subsystem.
  v4 — Adds aggregate columns to imports (date range, type counts, parse warnings).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlmodel import Session

CURRENT_SCHEMA_VERSION = 4


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
        return
    if current > CURRENT_SCHEMA_VERSION:
        raise RuntimeError(
            f"DB schema_version={current} is newer than this binary "
            f"(supports {CURRENT_SCHEMA_VERSION}). Upgrade net-alpha."
        )
