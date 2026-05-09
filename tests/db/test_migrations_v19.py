from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

import net_alpha.db.tables as _tables  # noqa: F401 — registers all SQLModel table classes
from net_alpha.db.migrations import get_schema_version, migrate


def test_v19_creates_service_run_table():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        migrate(s)
        rows = s.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name='service_run'")).all()
        assert len(rows) == 1


def test_v19_creates_washsale_watch_result_table():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        migrate(s)
        rows = s.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name='washsale_watch_result'")).all()
        assert len(rows) == 1


def test_v19_creates_accounts_table():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        migrate(s)
        rows = s.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'")).all()
        assert len(rows) == 1


def test_v19_idempotent():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        migrate(s)
        first_version = get_schema_version(s)
        migrate(s)
        assert get_schema_version(s) == first_version


def test_v19_advances_version_to_19():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        migrate(s)
        assert get_schema_version(s) == 19
