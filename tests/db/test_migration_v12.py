from sqlalchemy import create_engine, text
from sqlmodel import Session, SQLModel

import net_alpha.db.tables as _tables  # noqa: F401 — registers all SQLModel table classes
from net_alpha.db.migrations import migrate


def _v11_engine():
    """Return an in-memory engine at schema v11, with the tables that v12 should add absent."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        # Drop the tables v12 migration is supposed to create, then stamp v11.
        session.exec(text("DROP TABLE IF EXISTS position_targets"))
        session.exec(text("DROP TABLE IF EXISTS historical_price_cache"))
        session.exec(text("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', '11')"))
        session.commit()
    return engine


def test_v12_creates_position_targets_table():
    engine = _v11_engine()
    with Session(engine) as s:
        migrate(s)
        row = s.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name='position_targets'")).first()
        assert row is not None
        # Columns are correct.
        cols = {r[1] for r in s.exec(text("PRAGMA table_info(position_targets)")).all()}
        assert {"id", "symbol", "target_amount", "target_unit", "created_at", "updated_at"} <= cols


def test_v12_creates_historical_price_cache_table():
    engine = _v11_engine()
    with Session(engine) as s:
        migrate(s)
        row = s.exec(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='historical_price_cache'")
        ).first()
        assert row is not None


def test_v12_unique_symbol_constraint():
    from datetime import datetime

    engine = _v11_engine()
    with Session(engine) as s:
        migrate(s)
        now = datetime.utcnow().isoformat()
        s.exec(
            text(
                "INSERT INTO position_targets(symbol, target_amount, target_unit, created_at, updated_at) "
                "VALUES ('HIMS', 1000, 'usd', :n, :n)"
            ).bindparams(n=now)
        )
        s.commit()
        try:
            s.exec(
                text(
                    "INSERT INTO position_targets(symbol, target_amount, target_unit, created_at, updated_at) "
                    "VALUES ('HIMS', 2000, 'usd', :n, :n)"
                ).bindparams(n=now)
            )
            s.commit()
            raise AssertionError("Should have raised IntegrityError")
        except Exception as exc:
            assert "UNIQUE" in str(exc).upper()
