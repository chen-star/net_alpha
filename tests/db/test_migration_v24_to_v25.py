"""Migration v24 → v25: create overview_layout table."""

from __future__ import annotations

from sqlmodel import Session, text

from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.migrations import (
    CURRENT_SCHEMA_VERSION,
    _migrate_v24_to_v25,
    set_schema_version,
)


def test_v24_to_v25_creates_overview_layout_table(tmp_path):
    engine = get_engine(tmp_path / "x.db")
    init_db(engine)
    with Session(engine) as s:
        s.exec(text("DROP TABLE IF EXISTS overview_layout"))
        set_schema_version(s, 24)
        s.commit()
        _migrate_v24_to_v25(s)
        s.commit()
        cols = list(s.exec(text("PRAGMA table_info('overview_layout')")))
    names = {row[1] for row in cols}
    assert names == {"profile", "layout_json", "updated_at"}


def test_v24_to_v25_is_idempotent(tmp_path):
    engine = get_engine(tmp_path / "x.db")
    init_db(engine)
    with Session(engine) as s:
        _migrate_v24_to_v25(s)
        _migrate_v24_to_v25(s)  # second run must not raise
        s.commit()


def test_current_schema_version_is_26():
    assert CURRENT_SCHEMA_VERSION == 26
