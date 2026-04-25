from datetime import date

import pytest

from net_alpha.brokers.schwab import SchwabParser


def test_parses_simple_buy_and_sell():
    rows = [
        {
            "Date": "06/15/2024",
            "Action": "Buy",
            "Symbol": "TSLA",
            "Quantity": "10",
            "Price": "$200.00",
            "Amount": "$-2000.00",
        },
        {
            "Date": "08/01/2024",
            "Action": "Sell",
            "Symbol": "TSLA",
            "Quantity": "10",
            "Price": "$180.00",
            "Amount": "$1800.00",
        },
    ]
    trades = SchwabParser().parse(rows, account_display="schwab/personal")
    assert len(trades) == 2
    assert trades[0].action == "Buy"
    assert trades[0].cost_basis == 2000.0
    assert trades[0].date == date(2024, 6, 15)
    assert trades[1].action == "Sell"
    assert trades[1].proceeds == 1800.0


def test_skips_non_trade_rows():
    rows = [
        {
            "Date": "06/15/2024",
            "Action": "Cash Dividend",
            "Symbol": "TSLA",
            "Quantity": "",
            "Price": "",
            "Amount": "$25.00",
        },
    ]
    assert SchwabParser().parse(rows, account_display="schwab/personal") == []


def test_invalid_date_raises_with_row_number():
    rows = [
        {
            "Date": "13/40/9999",
            "Action": "Buy",
            "Symbol": "TSLA",
            "Quantity": "1",
            "Price": "1",
            "Amount": "$-1.00",
        }
    ]
    with pytest.raises(ValueError, match="Row 1"):
        SchwabParser().parse(rows, account_display="schwab/personal")


def test_reinvest_treated_as_buy():
    rows = [
        {
            "Date": "01/10/2024",
            "Action": "Reinvest Shares",
            "Symbol": "AAPL",
            "Quantity": "2",
            "Price": "$190.00",
            "Amount": "$-380.00",
        },
    ]
    trades = SchwabParser().parse(rows, account_display="schwab/personal")
    assert len(trades) == 1
    assert trades[0].action == "Buy"
    assert trades[0].cost_basis == 380.0


def test_buy_to_open_option():
    rows = [
        {
            "Date": "03/01/2024",
            "Action": "Buy to Open",
            "Symbol": "TSLA 03/21/2025 250.00 C",
            "Quantity": "1",
            "Price": "$5.00",
            "Amount": "$-500.00",
        },
    ]
    trades = SchwabParser().parse(rows, account_display="schwab/personal")
    assert len(trades) == 1
    assert trades[0].action == "Buy"
    assert trades[0].ticker == "TSLA"
    assert trades[0].option_details is not None
    assert trades[0].option_details.call_put == "C"
    assert trades[0].cost_basis == 500.0


def test_sell_to_close_option():
    rows = [
        {
            "Date": "03/21/2025",
            "Action": "Sell to Close",
            "Symbol": "TSLA 03/21/2025 250.00 C",
            "Quantity": "1",
            "Price": "$3.00",
            "Amount": "$300.00",
        },
    ]
    trades = SchwabParser().parse(rows, account_display="schwab/personal")
    assert len(trades) == 1
    assert trades[0].action == "Sell"
    assert trades[0].ticker == "TSLA"
    assert trades[0].proceeds == 300.0


def test_detect_requires_required_headers():
    parser = SchwabParser()
    assert parser.detect(["Date", "Action", "Symbol", "Quantity", "Amount"]) is True
    assert parser.detect(["Date", "Action", "Symbol", "Quantity"]) is False  # missing Amount
    assert parser.detect(["Date", "Action", "Symbol", "Quantity", "Amount", "Description", "Price"]) is True
