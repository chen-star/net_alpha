from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from net_alpha.db.migrations import (
    CURRENT_SCHEMA_VERSION,
    _table_exists,
    get_schema_version,
    migrate,
)


def test_migration_creates_price_cache_table(tmp_path):
    """Fresh DB → init_db creates price_cache, version stamped to 3."""
    import net_alpha.db.tables as _tables  # noqa: F401 — registers tables

    engine = create_engine(f"sqlite:///{tmp_path / 'x.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        migrate(s)
        assert _table_exists(s, "price_cache")
        assert get_schema_version(s) == 3
        assert CURRENT_SCHEMA_VERSION == 3


def test_v2_db_migrates_to_v3(tmp_path):
    """DB stamped at v2 with no price_cache table → migrate adds it and bumps version."""
    import net_alpha.db.tables as _tables  # noqa: F401

    engine = create_engine(f"sqlite:///{tmp_path / 'y.db'}")
    SQLModel.metadata.create_all(engine)

    # Seed the meta row by running migrate once (stamps v3).
    with Session(engine) as s:
        migrate(s)

    # Simulate a v2 DB: downgrade version stamp and remove price_cache.
    with Session(engine) as s:
        s.exec(text("UPDATE meta SET value='2' WHERE key='schema_version'"))
        s.exec(text("DROP TABLE IF EXISTS price_cache"))
        s.commit()
        assert not _table_exists(s, "price_cache")

    with Session(engine) as s:
        migrate(s)
        assert _table_exists(s, "price_cache")
        assert get_schema_version(s) == 3


def test_price_cache_roundtrip(tmp_path):
    """After migration the price_cache table accepts inserts and reads."""
    import net_alpha.db.tables as _tables  # noqa: F401

    engine = create_engine(f"sqlite:///{tmp_path / 'z.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        migrate(s)
        s.exec(
            text(
                "INSERT INTO price_cache(symbol, price, as_of, fetched_at, source) "
                "VALUES ('SPY', 460.5, :a, :f, 'yahoo')"
            ),
            params={"a": "2026-04-26T14:30:00+00:00", "f": datetime.now(UTC).isoformat()},
        )
        s.commit()
        row = s.exec(text("SELECT symbol, price, source FROM price_cache WHERE symbol='SPY'")).first()
        assert row[0] == "SPY"
        assert row[1] == 460.5
        assert row[2] == "yahoo"
