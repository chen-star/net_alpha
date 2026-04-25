# src/net_alpha/db/connection.py
from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

from net_alpha.db.migrations import CURRENT_SCHEMA_VERSION
from net_alpha.db.tables import MetaRow


def get_engine(db_path: Path):
    """Create a SQLAlchemy engine for the given SQLite database path."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", echo=False)


def init_db(engine) -> None:
    """Create all tables and set initial schema version if needed."""
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        existing = session.exec(select(MetaRow).where(MetaRow.key == "schema_version")).first()
        if existing is None:
            session.add(MetaRow(key="schema_version", value=str(CURRENT_SCHEMA_VERSION)))
            session.commit()
