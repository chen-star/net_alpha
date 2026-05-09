from datetime import date

import pytest

from net_alpha.brokers.robinhood import RobinhoodParser


def _row(**kw):
    base = {
        "Activity Date": "",
        "Process Date": "",
        "Settle Date": "",
        "Instrument": "",
        "Description": "",
        "Trans Code": "",
        "Quantity": "",
        "Price": "",
        "Amount": "",
    }
    base.update(kw)
    return base


def _parse(rows):
    return RobinhoodParser().parse_full(rows, "robinhood/personal")


def test_div_emits_dividend_cash_event():
    rows = [_row(
        **{"Activity Date": "10/15/2024", "Instrument": "AAPL", "Trans Code": "DIV",
           "Amount": "12.50", "Description": "Cash Div"}
    )]
    result = _parse(rows)
    assert len(result.cash_events) == 1
    ev = result.cash_events[0]
    assert ev.kind == "dividend"
    assert ev.amount == 12.50
    assert ev.event_date == date(2024, 10, 15)
    assert ev.ticker == "AAPL"


def test_int_emits_interest_cash_event():
    rows = [_row(
        **{"Activity Date": "10/31/2024", "Trans Code": "INT", "Amount": "1.23"}
    )]
    result = _parse(rows)
    assert len(result.cash_events) == 1
    assert result.cash_events[0].kind == "interest"
    assert result.cash_events[0].amount == 1.23


def test_gold_fee_emits_fee_cash_event():
    rows = [_row(
        **{"Activity Date": "10/01/2024", "Trans Code": "GOLD", "Amount": "-5.00"}
    )]
    result = _parse(rows)
    assert len(result.cash_events) == 1
    assert result.cash_events[0].kind == "fee"
    assert result.cash_events[0].amount == 5.00


def test_ach_in_emits_transfer_in():
    rows = [_row(
        **{"Activity Date": "09/01/2024", "Trans Code": "ACH", "Amount": "1000.00",
           "Description": "ACH Deposit"}
    )]
    result = _parse(rows)
    assert len(result.cash_events) == 1
    assert result.cash_events[0].kind == "transfer_in"
    assert result.cash_events[0].amount == 1000.00


def test_ach_out_emits_transfer_out():
    rows = [_row(
        **{"Activity Date": "09/15/2024", "Trans Code": "ACH", "Amount": "-200.00"}
    )]
    result = _parse(rows)
    assert result.cash_events[0].kind == "transfer_out"
    assert result.cash_events[0].amount == 200.00


def test_zero_amount_cash_event_is_skipped_with_warning():
    rows = [_row(
        **{"Activity Date": "10/15/2024", "Instrument": "AAPL", "Trans Code": "DIV",
           "Amount": "0"}
    )]
    result = _parse(rows)
    assert result.cash_events == []
    assert any("DIV" in w for w in result.parse_warnings)


def test_dividend_description_is_preserved():
    rows = [_row(
        **{"Activity Date": "10/15/2024", "Instrument": "AAPL", "Trans Code": "DIV",
           "Amount": "12.50", "Description": "AAPL Cash Div Q3 2024"}
    )]
    result = _parse(rows)
    assert result.cash_events[0].description == "AAPL Cash Div Q3 2024"


def test_acats_transfer_routes_correctly():
    rows = [_row(
        **{"Activity Date": "01/01/2024", "Trans Code": "ACATS", "Amount": "5000.00"}
    )]
    result = _parse(rows)
    assert result.cash_events[0].kind == "transfer_in"


def test_dividend_ticker_can_be_empty():
    rows = [_row(
        **{"Activity Date": "10/15/2024", "Trans Code": "INT", "Amount": "0.50"}
    )]
    result = _parse(rows)
    assert result.cash_events[0].ticker is None


@pytest.mark.parametrize("code", ["DIV", "DIVNRA", "CDIV"])
def test_all_dividend_aliases_route_to_dividend(code):
    rows = [_row(
        **{"Activity Date": "10/15/2024", "Instrument": "AAPL", "Trans Code": code,
           "Amount": "10.00"}
    )]
    result = _parse(rows)
    assert len(result.cash_events) == 1
    assert result.cash_events[0].kind == "dividend"
    assert result.cash_events[0].amount == 10.00


@pytest.mark.parametrize("code", ["GOLD", "MFEE", "MINT", "DTAX", "DFEE"])
def test_all_fee_aliases_route_to_fee(code):
    rows = [_row(
        **{"Activity Date": "10/01/2024", "Trans Code": code, "Amount": "-3.00"}
    )]
    result = _parse(rows)
    assert len(result.cash_events) == 1
    assert result.cash_events[0].kind == "fee"
    assert result.cash_events[0].amount == 3.00


def test_invalid_date_cash_event_is_skipped_with_warning():
    rows = [_row(
        **{"Activity Date": "BADDATE", "Instrument": "AAPL", "Trans Code": "DIV",
           "Amount": "12.50"}
    )]
    result = _parse(rows)
    assert result.cash_events == []
    assert any("DIV" in w and "Activity Date" in w for w in result.parse_warnings)
