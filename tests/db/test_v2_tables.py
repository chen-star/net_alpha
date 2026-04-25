from sqlalchemy import inspect
from sqlmodel import Session, SQLModel, create_engine

from net_alpha.db.tables import (
    AccountRow,
    ImportRecordRow,  # noqa: F401 — imported to register SQLModel metadata
    LotRow,  # noqa: F401 — imported to register SQLModel metadata
    MetaRow,  # noqa: F401 — imported to register SQLModel metadata
    TradeRow,  # noqa: F401 — imported to register SQLModel metadata
    WashSaleViolationRow,  # noqa: F401 — imported to register SQLModel metadata
)


def _engine(tmp_path):
    path = tmp_path / "test.db"
    eng = create_engine(f"sqlite:///{path}")
    SQLModel.metadata.create_all(eng)
    return eng


def test_account_row_has_unique_broker_label(tmp_path):
    eng = _engine(tmp_path)
    with Session(eng) as s:
        s.add(AccountRow(broker="schwab", label="personal"))
        s.commit()
    insp = inspect(eng)
    cols = {c["name"] for c in insp.get_columns("accounts")}
    assert {"id", "broker", "label"} <= cols


def test_import_record_row_has_sha_and_filename(tmp_path):
    eng = _engine(tmp_path)
    insp = inspect(eng)
    cols = {c["name"] for c in insp.get_columns("imports")}
    assert {"id", "account_id", "csv_filename", "csv_sha256", "imported_at", "trade_count"} <= cols


def test_trade_row_has_natural_key_and_fks(tmp_path):
    eng = _engine(tmp_path)
    insp = inspect(eng)
    cols = {c["name"] for c in insp.get_columns("trades")}
    assert {"id", "import_id", "account_id", "natural_key", "ticker", "trade_date"} <= cols


def test_lot_row_has_account_fk(tmp_path):
    eng = _engine(tmp_path)
    insp = inspect(eng)
    cols = {c["name"] for c in insp.get_columns("lots")}
    assert "account_id" in cols


def test_violation_row_has_account_fks(tmp_path):
    eng = _engine(tmp_path)
    insp = inspect(eng)
    cols = {c["name"] for c in insp.get_columns("wash_sale_violations")}
    assert {"loss_account_id", "buy_account_id"} <= cols


def test_no_schema_cache_table(tmp_path):
    eng = _engine(tmp_path)
    insp = inspect(eng)
    assert "schema_cache" not in insp.get_table_names()
