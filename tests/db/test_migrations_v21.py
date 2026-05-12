from sqlmodel import Session, create_engine, text

from net_alpha.db.migrations import (
    CURRENT_SCHEMA_VERSION,
    _migrate_v20_to_v21,
    set_schema_version,
)


def test_current_schema_version_is_23():
    assert CURRENT_SCHEMA_VERSION == 23


def test_v20_to_v21_creates_table_idempotently():
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as s:
        s.exec(text("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)"))
        set_schema_version(s, 20)
        _migrate_v20_to_v21(s)
        s.commit()

        row = s.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name='section_1256_mtm'")).first()
        assert row is not None

        # Idempotent — second call must not raise
        _migrate_v20_to_v21(s)
        s.commit()


def test_v20_to_v21_columns():
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as s:
        s.exec(text("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)"))
        set_schema_version(s, 20)
        _migrate_v20_to_v21(s)
        s.commit()
        cols = {r[1] for r in s.exec(text("PRAGMA table_info(section_1256_mtm)")).all()}
        assert {
            "id",
            "position_key",
            "tax_year",
            "last_business_day",
            "fmv",
            "basis_before",
            "unrealized_pnl",
            "long_term_portion",
            "short_term_portion",
            "fmv_source",
            "ticker",
            "account",
            "created_at",
        }.issubset(cols)
