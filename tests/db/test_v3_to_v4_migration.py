"""Schema migration test: v3 DB upgrades cleanly to v4 with new NULL columns."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, create_engine

from net_alpha.db.migrations import _migrate_v3_to_v4, get_schema_version, migrate, set_schema_version


def _build_v3_db(db_path: Path):
    """Construct a minimal v3-shape DB with a couple of import rows."""
    eng = create_engine(f"sqlite:///{db_path}", echo=False)
    with Session(eng) as s:
        s.exec(text("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)"))
        s.exec(text("CREATE TABLE accounts (id INTEGER PRIMARY KEY, broker TEXT, label TEXT)"))
        s.exec(
            text(
                "CREATE TABLE imports ("
                "id INTEGER PRIMARY KEY, account_id INTEGER, csv_filename TEXT, "
                "csv_sha256 TEXT, imported_at DATETIME, trade_count INTEGER)"
            )
        )
        s.exec(text("INSERT INTO accounts(broker, label) VALUES ('schwab', 'tax')"))
        s.exec(
            text(
                "INSERT INTO imports(account_id, csv_filename, csv_sha256, imported_at, trade_count) "
                "VALUES (1, 'old.csv', 'abc', '2026-01-01 00:00:00', 5)"
            )
        )
        s.commit()
        set_schema_version(s, 3)
    return eng


def test_v3_to_v4_adds_columns_and_bumps_version(tmp_path: Path):
    eng = _build_v3_db(tmp_path / "v3.db")
    with Session(eng) as s:
        assert get_schema_version(s) == 3
        migrate(s)
        # `migrate()` runs to head — every step up to CURRENT_SCHEMA_VERSION.
        from net_alpha.db.migrations import CURRENT_SCHEMA_VERSION

        assert get_schema_version(s) == CURRENT_SCHEMA_VERSION
        cols = {r[1] for r in s.exec(text("PRAGMA table_info(imports)")).all()}
        for col in [
            "min_trade_date",
            "max_trade_date",
            "equity_count",
            "option_count",
            "option_expiry_count",
            "parse_warnings_json",
            "duplicate_trades",
        ]:
            assert col in cols, f"missing column: {col}"
        # Existing row preserved with NULL aggregates.
        row = s.exec(text("SELECT min_trade_date, equity_count FROM imports WHERE id = 1")).first()
        assert row[0] is None
        assert row[1] is None


def test_v3_to_v4_idempotent(tmp_path: Path):
    eng = _build_v3_db(tmp_path / "v3.db")
    with Session(eng) as s:
        _migrate_v3_to_v4(s)
        # Run a second time — should not raise.
        _migrate_v3_to_v4(s)
        cols = {r[1] for r in s.exec(text("PRAGMA table_info(imports)")).all()}
        assert "min_trade_date" in cols
