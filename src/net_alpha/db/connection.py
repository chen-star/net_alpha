from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

import net_alpha.db.tables as _tables  # noqa: F401 — registers all SQLModel table classes
from net_alpha.db.migrations import migrate

# Meta key that marks the one-shot §1256 migration pass as complete.
_MIGRATION_1256_DONE_KEY = "section_1256_migration_done"


def get_engine(db_path: Path):
    """Create a SQLAlchemy engine for the given SQLite database path."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", echo=False)


def _migration_1256_done(engine) -> bool:
    """True iff the one-shot §1256 migration has already run on this DB."""
    with Session(engine) as s:
        row = s.exec(
            text("SELECT value FROM meta WHERE key=:k").bindparams(k=_MIGRATION_1256_DONE_KEY)
        ).first()
        return row is not None


def _stamp_migration_1256_done(engine) -> None:
    with Session(engine) as s:
        s.exec(
            text(
                "INSERT INTO meta(key, value) VALUES (:k, '1') "
                "ON CONFLICT(key) DO UPDATE SET value='1'"
            ).bindparams(k=_MIGRATION_1256_DONE_KEY)
        )
        s.commit()


def init_db(engine) -> None:
    """Create all tables (idempotent), run pending migrations, and backfill
    aggregate columns on legacy import rows. Also runs the one-shot §1256
    migration recompute pass on first launch after schema upgrade to v11."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        migrate(session)
    # Backfill must run after migrate so the v4 columns exist; uses its own
    # sessions internally via Repository.
    from net_alpha.db.repository import Repository
    from net_alpha.import_.backfill import backfill_import_aggregates

    repo = Repository(engine)
    backfill_import_aggregates(repo)

    # One-shot §1256 migration pass — runs exactly once per DB after the
    # v10→v11 schema upgrade. Reclassifies any stale §1256 wash-sale
    # violations as ExemptMatch records, backfills the is_section_1256 flag,
    # and runs the classifier over closed §1256 trades.
    if not _migration_1256_done(engine):
        from net_alpha.engine.recompute import migrate_existing_violations

        summary = migrate_existing_violations(repo)
        _stamp_migration_1256_done(engine)

        if summary.reclassified_count > 0 or summary.classifications_count > 0:
            print(
                "\nTax engine upgraded."
                f"\n  • {summary.reclassified_count} prior wash-sale violations reclassified as §1256 exempt"
                f"\n  • {summary.classifications_count} closed §1256 trades classified for 60/40 split"
                "\nRun with --detail or open the web UI for the full list.\n"
            )
