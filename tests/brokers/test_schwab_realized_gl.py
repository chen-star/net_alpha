from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from net_alpha.brokers.schwab_realized_gl import SchwabRealizedGLParser
from net_alpha.ingest.csv_loader import load_csv

FIXTURE = Path(__file__).parent / "fixtures" / "schwab_realized_gl_min.csv"


def test_detects_gl_headers():
    parser = SchwabRealizedGLParser()
    headers, _ = load_csv(str(FIXTURE))
    assert parser.detect(headers) is True


def test_does_not_detect_transactions_headers():
    parser = SchwabRealizedGLParser()
    assert parser.detect(["Date", "Action", "Symbol", "Quantity", "Amount"]) is False


def test_parse_returns_two_lots():
    parser = SchwabRealizedGLParser()
    headers, rows = load_csv(str(FIXTURE))
    lots = parser.parse(rows, account_display="schwab/personal")
    assert len(lots) == 2


def test_parse_stock_lot_fields():
    parser = SchwabRealizedGLParser()
    _, rows = load_csv(str(FIXTURE))
    lots = parser.parse(rows, account_display="schwab/personal")
    wrd = next(lot for lot in lots if lot.ticker == "WRD")
    assert wrd.symbol_raw == "WRD"
    assert wrd.closed_date == date(2026, 4, 20)
    assert wrd.opened_date == date(2026, 2, 11)
    assert wrd.quantity == 100.0
    assert wrd.proceeds == pytest.approx(824.96)
    assert wrd.cost_basis == pytest.approx(800.66)
    assert wrd.unadjusted_cost_basis == pytest.approx(800.66)
    assert wrd.wash_sale is False
    assert wrd.disallowed_loss == 0.0
    assert wrd.term == "Short Term"
    assert wrd.option_strike is None
    assert wrd.option_expiry is None
    assert wrd.option_call_put is None


def test_parse_option_lot_fields():
    parser = SchwabRealizedGLParser()
    _, rows = load_csv(str(FIXTURE))
    lots = parser.parse(rows, account_display="schwab/personal")
    crcl = next(lot for lot in lots if lot.ticker == "CRCL")
    assert crcl.symbol_raw == "CRCL 06/18/2026 150.00 C"
    assert crcl.option_strike == 150.00
    assert crcl.option_expiry == "2026-06-18"
    assert crcl.option_call_put == "C"
    assert crcl.wash_sale is True
    assert crcl.disallowed_loss == pytest.approx(130.33)


def test_parse_handles_empty_disallowed_loss_as_zero():
    parser = SchwabRealizedGLParser()
    _, rows = load_csv(str(FIXTURE))
    lots = parser.parse(rows, account_display="schwab/personal")
    wrd = next(lot for lot in lots if lot.ticker == "WRD")
    assert wrd.disallowed_loss == 0.0


def test_parser_name():
    assert SchwabRealizedGLParser().name == "schwab_realized_gl"
