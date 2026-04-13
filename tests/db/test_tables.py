# tests/db/test_tables.py
from net_alpha.db.tables import (
    LotRow,
    MetaRow,
    SchemaCacheRow,
    TradeRow,
    WashSaleViolationRow,
)


def test_trade_row_creation():
    row = TradeRow(
        id="t1",
        account="Schwab",
        date="2024-10-15",
        ticker="TSLA",
        action="Sell",
        quantity=10.0,
        proceeds=2400.0,
        cost_basis=3600.0,
        basis_unknown=False,
        raw_row_hash="abc123",
        schema_cache_id="sc1",
    )
    assert row.id == "t1"
    assert row.ticker == "TSLA"


def test_trade_row_with_option_fields():
    row = TradeRow(
        id="t2",
        account="Schwab",
        date="2024-10-15",
        ticker="TSLA",
        action="Buy",
        quantity=1.0,
        cost_basis=500.0,
        option_strike=250.0,
        option_expiry="2024-12-20",
        option_call_put="C",
    )
    assert row.option_strike == 250.0
    assert row.option_call_put == "C"


def test_lot_row_creation():
    row = LotRow(
        id="l1",
        trade_id="t1",
        account="Schwab",
        date="2024-10-15",
        ticker="TSLA",
        quantity=10.0,
        cost_basis=2400.0,
        adjusted_basis=2400.0,
    )
    assert row.adjusted_basis == 2400.0


def test_wash_sale_violation_row():
    row = WashSaleViolationRow(
        id="v1",
        loss_trade_id="t1",
        replacement_trade_id="t2",
        confidence="Confirmed",
        disallowed_loss=1200.0,
        matched_quantity=10.0,
    )
    assert row.confidence == "Confirmed"


def test_schema_cache_row():
    row = SchemaCacheRow(
        id="sc1",
        broker_name="schwab",
        header_hash="sha256abc",
        column_mapping='{"date": "Date", "ticker": "Symbol"}',
        option_format="schwab_human",
    )
    assert row.broker_name == "schwab"


def test_meta_row():
    row = MetaRow(key="schema_version", value="1")
    assert row.key == "schema_version"
