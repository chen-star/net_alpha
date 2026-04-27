"""v6 → v7: adds splits + lot_overrides tables."""

import pytest
from sqlalchemy import text
from sqlmodel import Session

from net_alpha.db.connection import get_engine
from net_alpha.db.migrations import migrate, set_schema_version


def test_v7_creates_splits_table(tmp_path):
    db_path = tmp_path / "v6.db"
    eng = get_engine(db_path)
    # Bootstrap empty DB at v6 (no schema present yet — set_schema_version expects meta to exist).
    with Session(eng) as s:
        s.exec(text("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)"))
        s.commit()
        set_schema_version(s, 6)

    with Session(eng) as s:
        migrate(s)

    with Session(eng) as s:
        row = s.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name='splits'")).first()
        assert row is not None, "splits table not created"
        cols = {r[1] for r in s.exec(text("PRAGMA table_info(splits)")).all()}
        assert {"symbol", "split_date", "ratio", "source", "fetched_at"} <= cols


def test_v7_creates_lot_overrides_table(tmp_path):
    db_path = tmp_path / "v6.db"
    eng = get_engine(db_path)
    with Session(eng) as s:
        s.exec(text("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)"))
        s.commit()
        set_schema_version(s, 6)

    with Session(eng) as s:
        migrate(s)

    with Session(eng) as s:
        row = s.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name='lot_overrides'")).first()
        assert row is not None
        cols = {r[1] for r in s.exec(text("PRAGMA table_info(lot_overrides)")).all()}
        assert {"trade_id", "field", "old_value", "new_value", "reason", "edited_at"} <= cols


def test_v7_splits_unique_symbol_split_date(tmp_path):
    db_path = tmp_path / "v6.db"
    eng = get_engine(db_path)
    with Session(eng) as s:
        s.exec(text("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)"))
        s.commit()
        set_schema_version(s, 6)
    with Session(eng) as s:
        migrate(s)

    with Session(eng) as s:
        s.exec(text(
            "INSERT INTO splits (symbol, split_date, ratio, source, fetched_at) "
            "VALUES ('AAPL', '2020-08-31', 4.0, 'yahoo', '2026-04-26T00:00:00Z')"
        ))
        s.commit()
        with pytest.raises(Exception):  # IntegrityError on duplicate key
            s.exec(text(
                "INSERT INTO splits (symbol, split_date, ratio, source, fetched_at) "
                "VALUES ('AAPL', '2020-08-31', 5.0, 'yahoo', '2026-04-26T00:00:00Z')"
            ))
            s.commit()
