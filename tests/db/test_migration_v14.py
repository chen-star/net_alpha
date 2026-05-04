"""v13 → v14: restore basis_source on transfer rows whose single-lot edit
overwrote it with 'user_set'."""

from sqlalchemy import create_engine, text
from sqlmodel import Session, SQLModel

import net_alpha.db.tables as _tables  # noqa: F401 — registers all SQLModel table classes
from net_alpha.db.migrations import migrate


def _v13_engine_with_buggy_transfer_rows():
    """Seed a v13 DB with one transfer-in and one transfer-out row whose
    basis_source has been clobbered to 'user_set' (the broken state we need
    to migrate). Also seed a non-transfer Buy with 'user_set' so we can
    verify it stays untouched."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.exec(text("INSERT INTO accounts(broker, label) VALUES ('Schwab', 'X')"))
        aid = s.exec(text("SELECT id FROM accounts LIMIT 1")).first()[0]
        # Transfer-in (Buy) with clobbered basis_source.
        s.exec(
            text(
                "INSERT INTO trades(account_id, natural_key, ticker, trade_date, action, quantity, "
                "cost_basis, basis_source, basis_unknown, transfer_date, transfer_basis_user_set, is_manual) "
                "VALUES (:aid, 'k1', 'NVDA', '2024-03-12', 'Buy', 10, 1500.0, 'user_set', 0, "
                "'2026-01-15', 0, 0)"
            ).bindparams(aid=aid)
        )
        # Transfer-out (Sell) with clobbered basis_source.
        s.exec(
            text(
                "INSERT INTO trades(account_id, natural_key, ticker, trade_date, action, quantity, "
                "proceeds, basis_source, basis_unknown, transfer_date, transfer_basis_user_set, is_manual) "
                "VALUES (:aid, 'k2', 'VOO', '2024-04-01', 'Sell', 5, 2000.0, 'user_set', 0, "
                "'2026-01-15', 0, 0)"
            ).bindparams(aid=aid)
        )
        # Non-transfer Buy with user_set: must remain unchanged (no transfer_date).
        s.exec(
            text(
                "INSERT INTO trades(account_id, natural_key, ticker, trade_date, action, quantity, "
                "cost_basis, basis_source, basis_unknown, transfer_date, transfer_basis_user_set, is_manual) "
                "VALUES (:aid, 'k3', 'AAPL', '2024-05-01', 'Buy', 1, 199.99, 'user_set', 0, NULL, 0, 0)"
            ).bindparams(aid=aid)
        )
        s.exec(text("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', '13')"))
        s.commit()
    return engine


def test_v14_restores_basis_source_on_transfer_in():
    engine = _v13_engine_with_buggy_transfer_rows()
    with Session(engine) as s:
        migrate(s)
        row = s.exec(text("SELECT basis_source, transfer_basis_user_set FROM trades WHERE natural_key='k1'")).first()
        assert row[0] == "transfer_in"
        assert row[1] == 1


def test_v14_restores_basis_source_on_transfer_out():
    engine = _v13_engine_with_buggy_transfer_rows()
    with Session(engine) as s:
        migrate(s)
        row = s.exec(text("SELECT basis_source, transfer_basis_user_set FROM trades WHERE natural_key='k2'")).first()
        assert row[0] == "transfer_out"
        assert row[1] == 1


def test_v14_leaves_non_transfer_user_set_untouched():
    engine = _v13_engine_with_buggy_transfer_rows()
    with Session(engine) as s:
        migrate(s)
        row = s.exec(text("SELECT basis_source FROM trades WHERE natural_key='k3'")).first()
        assert row[0] == "user_set"


def test_migration_chain_from_v13_reaches_current_version():
    from net_alpha.db.migrations import CURRENT_SCHEMA_VERSION

    engine = _v13_engine_with_buggy_transfer_rows()
    with Session(engine) as s:
        migrate(s)
        v = s.exec(text("SELECT value FROM meta WHERE key='schema_version'")).first()
        assert v[0] == str(CURRENT_SCHEMA_VERSION)


def test_v14_idempotent():
    engine = _v13_engine_with_buggy_transfer_rows()
    with Session(engine) as s:
        migrate(s)
    with Session(engine) as s:
        migrate(s)  # second run is a no-op
    with Session(engine) as s:
        row = s.exec(text("SELECT basis_source FROM trades WHERE natural_key='k1'")).first()
        assert row[0] == "transfer_in"
