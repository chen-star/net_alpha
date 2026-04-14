# tests/db/test_connection.py
import tempfile
from pathlib import Path

from sqlmodel import Session, select

from net_alpha.db.connection import CURRENT_SCHEMA_VERSION, get_engine, init_db
from net_alpha.db.migrations import run_migrations
from net_alpha.db.tables import MetaRow, TradeRow


def test_init_db_creates_tables():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        engine = get_engine(db_path)
        init_db(engine)

        with Session(engine) as session:
            # Tables should exist — inserting should work
            row = TradeRow(
                id="t1",
                account="Schwab",
                date="2024-10-15",
                ticker="TSLA",
                action="Buy",
                quantity=10.0,
            )
            session.add(row)
            session.commit()

            result = session.exec(select(TradeRow)).first()
            assert result is not None
            assert result.ticker == "TSLA"


def test_init_db_sets_schema_version():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        engine = get_engine(db_path)
        init_db(engine)

        with Session(engine) as session:
            meta = session.exec(select(MetaRow).where(MetaRow.key == "schema_version")).first()
            assert meta is not None
            assert int(meta.value) >= 1


def test_init_db_idempotent():
    """Calling init_db twice should not error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        engine = get_engine(db_path)
        init_db(engine)
        init_db(engine)  # Should not raise


def test_run_migrations_noop_when_current():
    """No migrations needed when DB is already at current version."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        engine = get_engine(db_path)
        init_db(engine)
        run_migrations(engine)  # Should not raise

        with Session(engine) as session:
            meta = session.exec(select(MetaRow).where(MetaRow.key == "schema_version")).first()
            assert int(meta.value) == CURRENT_SCHEMA_VERSION


def test_run_migrations_updates_version():
    """Migrations bring schema_version to current."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        engine = get_engine(db_path)
        init_db(engine)

        # Simulate old version
        with Session(engine) as session:
            meta = session.exec(select(MetaRow).where(MetaRow.key == "schema_version")).first()
            meta.value = "0"
            session.add(meta)
            session.commit()

        run_migrations(engine)

        with Session(engine) as session:
            meta = session.exec(select(MetaRow).where(MetaRow.key == "schema_version")).first()
            assert int(meta.value) == CURRENT_SCHEMA_VERSION
