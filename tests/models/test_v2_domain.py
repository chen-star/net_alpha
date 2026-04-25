from datetime import date, datetime
from decimal import Decimal

from net_alpha.models.domain import (
    Account,
    AddImportResult,
    ImportRecord,
    ImportSummary,
    LotConsumption,
    RemoveImportResult,
    SimulationOption,
)


def test_account_has_broker_and_label():
    a = Account(broker="schwab", label="personal")
    assert a.broker == "schwab"
    assert a.label == "personal"
    assert a.display() == "schwab/personal"


def test_import_record_has_filename_sha_and_count():
    r = ImportRecord(
        account_id=1,
        csv_filename="q1.csv",
        csv_sha256="abc",
        imported_at=datetime(2026, 4, 25, 10, 0),
        trade_count=412,
    )
    assert r.csv_filename == "q1.csv"
    assert r.trade_count == 412


def test_add_import_result_reports_new_and_dup_counts():
    r = AddImportResult(import_id=1, new_trades=298, duplicate_trades=4)
    assert r.new_trades == 298
    assert r.duplicate_trades == 4


def test_remove_import_result_reports_removed():
    r = RemoveImportResult(removed_trade_count=298, recompute_window=(date(2024, 8, 16), date(2024, 10, 24)))
    assert r.removed_trade_count == 298


def test_import_summary_has_display_account():
    s = ImportSummary(
        id=1,
        account_display="schwab/personal",
        csv_filename="q1.csv",
        trade_count=412,
        imported_at=datetime(2026, 4, 25, 10, 0),
    )
    assert s.account_display == "schwab/personal"


def test_lot_consumption_records_lot_qty_and_basis():
    lc = LotConsumption(
        lot_id=7, quantity=Decimal("5"), basis_per_share=Decimal("200"), purchase_date=date(2024, 8, 15)
    )
    assert lc.quantity == Decimal("5")


def test_simulation_option_carries_account_pnl_and_wash_verdict():
    acct = Account(broker="schwab", label="personal")
    opt = SimulationOption(
        account=acct,
        lots_consumed_fifo=[],
        realized_pnl=Decimal("-150"),
        would_trigger_wash_sale=True,
        blocking_buys=[],
        lookforward_block_until=None,
        confidence="Confirmed",
        insufficient_shares=False,
        available_shares=Decimal("10"),
    )
    assert opt.would_trigger_wash_sale is True
    assert opt.realized_pnl == Decimal("-150")
