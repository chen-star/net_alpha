"""Demo data + fixture builder for the onboarding tour."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from net_alpha.web.demo.fixture import build_demo_db


def ensure_demo_db(target: Path) -> None:
    """Build the demo SQLite if missing, empty, or schema-stale.

    A 0-byte ``demo.db`` can be left behind by an aborted SQLite open
    (e.g. an earlier render touched the path before initialization),
    which then trips up callers expecting the schema to exist. A demo.db
    written by an older release is worse: it has the ``accounts`` table
    but lags the current schema (e.g. missing ``accounts.broker_label``),
    so the SQLModel models select a column SQLite doesn't have and the
    dashboard 500s. The demo DB is disposable, so regenerate it whenever
    its ``schema_version`` is behind. This makes demo-mode self-healing.
    """
    from net_alpha.db.migrations import CURRENT_SCHEMA_VERSION

    target = Path(target)
    if not target.exists() or target.stat().st_size == 0:
        build_demo_db(target)
        return
    try:
        with sqlite3.connect(target) as conn:
            row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'").fetchone()
            if row is None:
                build_demo_db(target)
                return
            ver_row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if ver_row is None or int(ver_row[0]) < CURRENT_SCHEMA_VERSION:
            build_demo_db(target)
    except (sqlite3.DatabaseError, ValueError):
        build_demo_db(target)


__all__ = ["build_demo_db", "ensure_demo_db"]
