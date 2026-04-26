from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

import net_alpha.db.tables as _tables  # noqa: F401 — registers all SQLModel table classes
from net_alpha.db.migrations import migrate


def get_engine(db_path: Path):
    """Create a SQLAlchemy engine for the given SQLite database path."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", echo=False)


def init_db(engine) -> None:
    """Create all tables (idempotent), run pending migrations, and backfill
    aggregate columns on legacy import rows."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        migrate(session)
    # Backfill must run after migrate so the v4 columns exist; uses its own
    # sessions internally via Repository.
    from net_alpha.db.repository import Repository
    from net_alpha.import_.backfill import backfill_import_aggregates

    backfill_import_aggregates(Repository(engine))
