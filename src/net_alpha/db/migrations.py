# src/net_alpha/db/migrations.py
from __future__ import annotations

from sqlmodel import Session, select

from net_alpha.db.connection import CURRENT_SCHEMA_VERSION
from net_alpha.db.tables import MetaRow


def run_migrations(engine) -> None:
    """Run hand-written migrations to bring DB to current schema version.

    Each migration documents the behavioral implication of NULL values
    in newly added columns and specifies the fallback explicitly.
    """
    with Session(engine) as session:
        meta = session.exec(select(MetaRow).where(MetaRow.key == "schema_version")).first()
        if meta is None:
            return

        current = int(meta.value)

        if current < 1:
            _migrate_v0_to_v1(session)
            current = 1

        # Future migrations go here:
        # if current < 2:
        #     _migrate_v1_to_v2(session)
        #     current = 2

        meta.value = str(CURRENT_SCHEMA_VERSION)
        session.add(meta)
        session.commit()


def _migrate_v0_to_v1(session: Session) -> None:
    """v0 → v1: Initial schema. All tables created by init_db.

    Migration v0→v1 is a no-op because init_db already creates all v1 tables.
    This exists as a placeholder for the migration framework pattern.

    NULL policy for v1 columns:
    - raw_row_hash IS NULL → trade was imported before dedup was added;
      dedup logic treats NULL as "use semantic key only"
    - schema_cache_id IS NULL → trade was imported before schema caching;
      option parser falls back to best-effort cascade
    """
    pass
