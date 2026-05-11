from __future__ import annotations

from pathlib import Path

import pytest

from net_alpha.import_.positions_csv import (
    PositionsCSVParseError,
    parse_positions_csv,
)

FIXTURE = Path(__file__).parent / "golden" / "cases" / "schwab_positions_sample.csv"


def test_parser_extracts_as_of_date_from_header():
    rows, as_of = parse_positions_csv(FIXTURE.read_text())
    assert as_of == "2026-05-10"


def test_parser_extracts_all_position_rows():
    rows, _ = parse_positions_csv(FIXTURE.read_text())
    assert len(rows) == 3
    aapl = next(r for r in rows if r["symbol"] == "AAPL")
    assert aapl["account_label"] == "Schwab-Taxable"
    assert aapl["qty"] == 100.0
    assert aapl["cost_basis"] == 15000.0
    assert aapl["market_value"] == 17550.0
    assert aapl["unrealized_pl"] == 2550.0


def test_parser_skips_total_rows():
    rows, _ = parse_positions_csv(FIXTURE.read_text())
    assert not any(r.get("symbol") in {"", "Account Total"} for r in rows)


def test_parser_rejects_csv_without_as_of_header():
    bad = "Account,Symbol,Quantity\nFoo,AAPL,100\n"
    with pytest.raises(PositionsCSVParseError, match="as-of"):
        parse_positions_csv(bad)


def test_parser_rejects_unparseable_date():
    bad = '"Positions for All Accounts as of garbage"\nAccount,Symbol\nFoo,X\n'
    with pytest.raises(PositionsCSVParseError, match="as-of"):
        parse_positions_csv(bad)
