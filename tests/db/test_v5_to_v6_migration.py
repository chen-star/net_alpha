from __future__ import annotations

from sqlalchemy import text
from sqlmodel import Session

from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.migrations import (
    CURRENT_SCHEMA_VERSION,
    _column_exists,
    get_schema_version,
    migrate,
    set_schema_version,
)


def _force_v5(session: Session) -> None:
    """Pretend the DB is v5: drop the new v6 columns if present, set version."""
    set_schema_version(session, 5)


def test_v5_to_v6_adds_new_columns(tmp_path):
    """Test that migrating from v5 adds is_manual and transfer_basis_user_set columns.

    NOTE: init_db calls SQLModel.metadata.create_all which builds tables from
    TradeRow — which does NOT yet include is_manual or transfer_basis_user_set
    (those are added in Task 2). So init_db produces a v5-style schema without
    those columns. We skip the DROP COLUMN calls from the original plan (they
    would fail since the columns don't exist), and instead just stamp v5 then
    run migrate() to verify the columns are added.
    """
    db_path = tmp_path / "db.sqlite"
    engine = get_engine(db_path)
    init_db(engine)  # creates tables without the new v6 columns (TradeRow lacks them)
    with Session(engine) as s:
        assert not _column_exists(s, "trades", "is_manual"), (
            "is_manual should not exist yet — TradeRow hasn't been updated to v6"
        )
        assert not _column_exists(s, "trades", "transfer_basis_user_set"), (
            "transfer_basis_user_set should not exist yet — TradeRow hasn't been updated to v6"
        )
        _force_v5(s)
        s.commit()
    with Session(engine) as s:
        assert get_schema_version(s) == 5
        migrate(s)
        assert get_schema_version(s) == CURRENT_SCHEMA_VERSION
        assert _column_exists(s, "trades", "is_manual")
        assert _column_exists(s, "trades", "transfer_basis_user_set")


def test_v5_to_v6_relaxes_import_id_not_null(tmp_path):
    """After migration, inserting a trade with import_id=NULL must succeed."""
    db_path = tmp_path / "db.sqlite"
    engine = get_engine(db_path)
    init_db(engine)
    with Session(engine) as s:
        # Stamp v5 so migrate() will run the v5→v6 step (which includes the rebuild dance)
        _force_v5(s)
        s.commit()
    with Session(engine) as s:
        migrate(s)
    with Session(engine) as s:
        s.exec(text("INSERT INTO accounts(broker, label) VALUES ('Schwab','Tax')"))
        s.commit()
    with Session(engine) as s:
        s.exec(
            text(
                "INSERT INTO trades(import_id, account_id, natural_key, ticker, trade_date, "
                "action, quantity, basis_source, is_manual, transfer_basis_user_set) "
                "VALUES (NULL, 1, 'manual:abc', 'AAPL', '2026-01-15', 'Buy', 10, 'user', 1, 0)"
            )
        )
        s.commit()
        row = s.exec(text("SELECT id, import_id, is_manual FROM trades WHERE natural_key='manual:abc'")).first()
        assert row is not None
        assert row[1] is None
        assert row[2] == 1
