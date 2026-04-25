# src/net_alpha/db/migrations.py
"""Hand-written migrations. v2 starts at schema_version=1.

v1 → v2 is a clean break. Users either re-import their CSVs or run
`net-alpha migrate-from-v1`. There is no in-place upgrade.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlmodel import Session

CURRENT_SCHEMA_VERSION = 1


def get_schema_version(session: Session) -> int:
    row = session.exec(text("SELECT value FROM meta WHERE key='schema_version'")).first()
    return int(row[0]) if row else 0


def set_schema_version(session: Session, version: int) -> None:
    session.exec(
        text("INSERT INTO meta(key, value) VALUES ('schema_version', :v) ON CONFLICT(key) DO UPDATE SET value=:v"),
        params={"v": str(version)},
    )
    session.commit()


def migrate(session: Session) -> None:
    """Apply pending migrations. v2.0.0 is schema_version=1 — no upgrades exist yet."""
    current = get_schema_version(session)
    if current == 0:
        set_schema_version(session, CURRENT_SCHEMA_VERSION)
        return
    if current > CURRENT_SCHEMA_VERSION:
        raise RuntimeError(
            f"DB schema_version={current} is newer than this binary "
            f"(supports {CURRENT_SCHEMA_VERSION}). Upgrade net-alpha."
        )
    # Add upgrade branches here when adding schema_version=2, 3, ...
