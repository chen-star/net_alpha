"""v22 → v23: wash_sale_violations.kind for Rev. Rul. 2008-5 permanent disallowance."""

from sqlmodel import Session, create_engine, text

from net_alpha.db.migrations import (
    CURRENT_SCHEMA_VERSION,
    _migrate_v22_to_v23,
    set_schema_version,
)


def test_current_schema_version_is_24():
    assert CURRENT_SCHEMA_VERSION == 24


def test_v22_to_v23_adds_kind_column_with_default_deferred():
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as s:
        s.exec(text("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)"))
        # Minimal wash_sale_violations table the migration expects.
        s.exec(
            text(
                "CREATE TABLE wash_sale_violations ("
                "id INTEGER PRIMARY KEY, loss_trade_id INTEGER, "
                "replacement_trade_id INTEGER, loss_account_id INTEGER, "
                "buy_account_id INTEGER, loss_sale_date TEXT, "
                "triggering_buy_date TEXT, ticker TEXT, confidence TEXT, "
                "disallowed_loss REAL, matched_quantity REAL, source TEXT)"
            )
        )
        # Seed one pre-existing row to verify the default backfills.
        s.exec(
            text(
                "INSERT INTO wash_sale_violations "
                "(loss_trade_id, replacement_trade_id, loss_account_id, buy_account_id, "
                "loss_sale_date, triggering_buy_date, ticker, confidence, "
                "disallowed_loss, matched_quantity, source) "
                "VALUES (1, 2, 1, 1, '2025-01-01', '2025-01-15', 'AAPL', "
                "'Confirmed', 100.0, 10.0, 'engine')"
            )
        )
        set_schema_version(s, 22)

        _migrate_v22_to_v23(s)
        s.commit()

        cols = {r[1] for r in s.exec(text("PRAGMA table_info(wash_sale_violations)")).all()}
        assert "kind" in cols

        # Pre-existing row backfilled to "deferred"
        existing = s.exec(text("SELECT kind FROM wash_sale_violations WHERE id=1")).first()
        assert existing[0] == "deferred"

        # Idempotent
        _migrate_v22_to_v23(s)
        s.commit()


def test_v22_to_v23_no_op_when_table_missing():
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as s:
        s.exec(text("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)"))
        set_schema_version(s, 22)
        _migrate_v22_to_v23(s)  # must not raise
        s.commit()
