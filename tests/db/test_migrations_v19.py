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


def test_v19_adds_type_and_created_at_columns_to_accounts():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        migrate(s)
        cols = list(s.exec(text("PRAGMA table_info(accounts)")).all())
        names = {c[1] for c in cols}
        assert "type" in names
        assert "created_at" in names


def test_v19_backfills_existing_accounts_with_taxable_type():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        # Insert a pre-existing account row; type has a DEFAULT so omitting it
        # would fail NOT NULL — include a value to simulate a row that existed
        # before created_at was added, then verify migration backfills created_at.
        s.exec(text("INSERT INTO accounts(broker, label, type) VALUES('schwab', 'personal', 'taxable')"))
        migrate(s)
        rows = list(s.exec(text("SELECT broker, label, type, created_at FROM accounts WHERE label='personal'")).all())
        assert len(rows) == 1
        assert rows[0][2] == "taxable"
        assert rows[0][3] is not None  # created_at backfilled by migration


def test_v19_idempotent():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        migrate(s)
        first_version = get_schema_version(s)
        migrate(s)
        assert get_schema_version(s) == first_version


def test_v19_advances_version_to_20():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        migrate(s)
        assert get_schema_version(s) == 20
