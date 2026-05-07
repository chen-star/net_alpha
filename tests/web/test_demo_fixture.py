from __future__ import annotations

from net_alpha.web.demo.data import DEMO_IRA, DEMO_TAXABLE


def test_demo_taxable_has_expected_row_count() -> None:
    assert len(DEMO_TAXABLE) >= 18


def test_demo_ira_has_expected_row_count() -> None:
    assert len(DEMO_IRA) >= 8


def test_demo_rows_use_required_schwab_columns() -> None:
    required = {"Date", "Action", "Symbol", "Quantity", "Price", "Amount"}
    for row in DEMO_TAXABLE + DEMO_IRA:
        assert required <= row.keys(), f"missing columns in row {row}"


def test_demo_taxable_includes_tsla_wash_sale_round_trip() -> None:
    """Confirmed wash sale: Buy TSLA, sell at loss, rebuy within 30 days."""
    tsla_actions = [r for r in DEMO_TAXABLE if r["Symbol"] == "TSLA"]
    actions = [r["Action"] for r in tsla_actions]
    assert actions.count("Buy") >= 2
    assert actions.count("Sell") >= 1


def test_demo_includes_section_1256_spx() -> None:
    rows = DEMO_TAXABLE + DEMO_IRA
    assert any(r["Symbol"].startswith("SPX") for r in rows)


def test_demo_includes_options() -> None:
    rows = DEMO_TAXABLE + DEMO_IRA
    option_rows = [r for r in rows if r["Action"] in {"Buy to Open", "Sell to Close", "Sell to Open", "Buy to Close"}]
    assert len(option_rows) >= 6
