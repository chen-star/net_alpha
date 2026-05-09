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
    return RobinhoodParser().parse(rows, "robinhood/personal")


def test_parses_simple_buy():
    rows = [_row(
        **{"Activity Date": "10/15/2024", "Instrument": "TSLA", "Trans Code": "Buy",
           "Quantity": "10", "Price": "240.00", "Amount": "-2400.00"}
    )]
    trades = _parse(rows)
    assert len(trades) == 1
    assert trades[0].action == "Buy"
    assert trades[0].ticker == "TSLA"
    assert trades[0].quantity == 10.0
    assert trades[0].cost_basis == 2400.0
    assert trades[0].date == date(2024, 10, 15)


def test_parses_simple_sell():
    rows = [_row(
        **{"Activity Date": "10/20/2024", "Instrument": "TSLA", "Trans Code": "Sell",
           "Quantity": "10", "Price": "200.00", "Amount": "2000.00"}
    )]
    trades = _parse(rows)
    assert len(trades) == 1
    assert trades[0].action == "Sell"
    assert trades[0].proceeds == 2000.0
    assert trades[0].cost_basis is None


def test_invalid_date_raises_with_row_number():
    rows = [_row(
        **{"Activity Date": "13/40/9999", "Instrument": "TSLA", "Trans Code": "Buy",
           "Quantity": "1", "Price": "1", "Amount": "-1.00"}
    )]
    with pytest.raises(ValueError, match="Row 1"):
        _parse(rows)


def test_bto_parses_as_buy_with_option_details():
    rows = [_row(
        **{"Activity Date": "10/25/2024", "Instrument": "TSLA $250 Call 12/20/2024",
           "Trans Code": "BTO", "Quantity": "1", "Price": "5.00", "Amount": "-500.00"}
    )]
    trades = _parse(rows)
    assert len(trades) == 1
    assert trades[0].action == "Buy"
    assert trades[0].ticker == "TSLA"
    assert trades[0].cost_basis == 500.0
    assert trades[0].option_details is not None
    assert trades[0].option_details.strike == 250.0
    assert trades[0].option_details.call_put == "C"
    assert trades[0].option_details.expiry == date(2024, 12, 20)
    assert trades[0].basis_source == "unknown"


def test_stc_parses_as_sell_with_option_details():
    rows = [_row(
        **{"Activity Date": "11/01/2024", "Instrument": "TSLA $250 Call 12/20/2024",
           "Trans Code": "STC", "Quantity": "1", "Price": "8.00", "Amount": "800.00"}
    )]
    trades = _parse(rows)
    assert len(trades) == 1
    assert trades[0].action == "Sell"
    assert trades[0].proceeds == 800.0
    assert trades[0].option_details is not None


def test_sto_parses_as_sell_with_short_open_marker():
    rows = [_row(
        **{"Activity Date": "10/25/2024", "Instrument": "TSLA $250 Put 12/20/2024",
           "Trans Code": "STO", "Quantity": "1", "Price": "3.00", "Amount": "300.00"}
    )]
    trades = _parse(rows)
    assert len(trades) == 1
    assert trades[0].action == "Sell"
    assert trades[0].proceeds == 300.0
    assert trades[0].basis_source == "option_short_open"


def test_btc_parses_as_buy_with_short_close_marker():
    rows = [_row(
        **{"Activity Date": "11/01/2024", "Instrument": "TSLA $250 Put 12/20/2024",
           "Trans Code": "BTC", "Quantity": "1", "Price": "1.00", "Amount": "-100.00"}
    )]
    trades = _parse(rows)
    assert len(trades) == 1
    assert trades[0].action == "Buy"
    assert trades[0].cost_basis == 100.0
    assert trades[0].basis_source == "option_short_close"


def test_oexp_emits_no_trade():
    rows = [_row(
        **{"Activity Date": "12/20/2024", "Instrument": "TSLA $300 Call 12/20/2024",
           "Trans Code": "OEXP", "Quantity": "1", "Price": "0", "Amount": "0"}
    )]
    trades = _parse(rows)
    assert trades == []


def test_oexp_does_not_warn():
    rows = [_row(
        **{"Activity Date": "12/20/2024", "Instrument": "TSLA $300 Call 12/20/2024",
           "Trans Code": "OEXP", "Quantity": "1", "Price": "0", "Amount": "0"}
    )]
    result = RobinhoodParser().parse_full(rows, "robinhood/personal")
    assert result.parse_warnings == []
