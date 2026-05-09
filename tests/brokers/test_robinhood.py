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
