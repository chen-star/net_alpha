"""Demo data + fixture builder for the onboarding tour."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from net_alpha.web.demo.fixture import build_demo_db


def ensure_demo_db(target: Path) -> None:
    """Build the demo SQLite if missing, empty, or schema-incomplete.

    A 0-byte ``demo.db`` can be left behind by an aborted SQLite open
    (e.g. an earlier render touched the path before initialization),
    which then trips up callers expecting the schema to exist. This
    helper makes the demo-mode entry points self-healing.
    """
    target = Path(target)
    if not target.exists() or target.stat().st_size == 0:
        build_demo_db(target)
        return
    try:
        with sqlite3.connect(target) as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'"
            ).fetchone()
        if row is None:
            build_demo_db(target)
    except sqlite3.DatabaseError:
        build_demo_db(target)


__all__ = ["build_demo_db", "ensure_demo_db"]
