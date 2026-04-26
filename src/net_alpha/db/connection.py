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
    """Create all tables (idempotent) and run pending migrations."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        migrate(session)
