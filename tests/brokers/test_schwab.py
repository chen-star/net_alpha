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


def test_journaled_shares_out_is_transfer_out_sell():
    # Schwab's `Journaled Shares` row with a negative qty represents shares
    # leaving this account (e.g. moved to another account of the same owner).
    # Must consume open lots without producing realized P/L.
    rows = [
        {
            "Date": "06/26/2025",
            "Action": "Journaled Shares",
            "Symbol": "WRD",
            "Quantity": "-100",
            "Price": "$8.25",
            "Amount": "",
        }
    ]
    trades = SchwabParser().parse(rows, account_display="schwab/lt")
    assert len(trades) == 1
    t = trades[0]
    assert t.action == "Sell"
    assert t.quantity == 100
    assert t.proceeds is None
    assert t.cost_basis is None
    assert t.basis_unknown is True
    assert t.basis_source == "transfer_out"


def test_journaled_shares_in_uses_price_as_basis_estimate():
    rows = [
        {
            "Date": "06/26/2025",
            "Action": "Journaled Shares",
            "Symbol": "WRD",
            "Quantity": "100",
            "Price": "$8.25",
            "Amount": "",
        }
    ]
    trades = SchwabParser().parse(rows, account_display="schwab/st")
    assert len(trades) == 1
    t = trades[0]
    assert t.action == "Buy"
    assert t.quantity == 100
    assert t.cost_basis == 825.0
    assert t.basis_unknown is True
    assert t.basis_source == "transfer_in"


def test_security_transfer_in_has_no_basis():
    # Security Transfer rows have no Price and no Amount — basis is unknown.
    rows = [
        {
            "Date": "04/14/2025",
            "Action": "Security Transfer",
            "Symbol": "NVDA",
            "Quantity": "4",
            "Price": "",
            "Amount": "",
        }
    ]
    trades = SchwabParser().parse(rows, account_display="schwab/lt")
    assert len(trades) == 1
    t = trades[0]
    assert t.action == "Buy"
    assert t.quantity == 4
    assert t.cost_basis is None
    assert t.basis_unknown is True
    assert t.basis_source == "transfer_in"


def test_security_transfer_out_with_negative_qty():
    rows = [
        {
            "Date": "04/14/2025",
            "Action": "Security Transfer",
            "Symbol": "NVDA",
            "Quantity": "-4",
            "Price": "",
            "Amount": "",
        }
    ]
    trades = SchwabParser().parse(rows, account_display="schwab/lt")
    assert len(trades) == 1
    t = trades[0]
    assert t.action == "Sell"
    assert t.quantity == 4
    assert t.proceeds is None
    assert t.basis_source == "transfer_out"


def test_zero_quantity_transfer_skipped():
    rows = [
        {
            "Date": "04/14/2025",
            "Action": "Security Transfer",
            "Symbol": "NVDA",
            "Quantity": "0",
            "Price": "",
            "Amount": "",
        }
    ]
    assert SchwabParser().parse(rows, account_display="schwab/lt") == []


def test_assigned_short_put_reduces_underlying_basis_by_premium():
    # IRS Pub 550: premium received on a written put reduces the basis of
    # stock acquired by exercise. Schwab's Transactions CSV records the
    # assignment as Buy at strike (no adjustment), so we must subtract here.
    rows = [
        {
            "Date": "02/26/2026",
            "Action": "Sell to Open",
            "Symbol": "EOSE 04/17/2026 10.00 P",
            "Quantity": "1",
            "Price": "$2.99",
            "Amount": "$298.34",
        },
        {
            "Date": "03/25/2026 as of 03/24/2026",
            "Action": "Assigned",
            "Symbol": "EOSE 04/17/2026 10.00 P",
            "Quantity": "1",
            "Price": "",
            "Amount": "",
        },
        {
            "Date": "03/25/2026 as of 03/24/2026",
            "Action": "Buy",
            "Symbol": "EOSE",
            "Quantity": "100",
            "Price": "$10.00",
            "Amount": "-$1000.00",
        },
    ]
    trades = SchwabParser().parse(rows, account_display="schwab/st")
    eose = [t for t in trades if t.ticker == "EOSE" and t.option_details is None]
    assert len(eose) == 1
    assert eose[0].action == "Buy"
    assert eose[0].quantity == 100
    assert eose[0].cost_basis == pytest.approx(701.66, abs=0.01)  # 1000 - 298.34
    assert eose[0].basis_source == "put_assignment"


def test_assigned_short_put_with_partial_close_uses_net_premium():
    # User opens 2 contracts at $200 each, closes 1 at $50, has 1 remaining
    # contract assigned. Net premium = (400 - 50) / 2 = $175 per contract,
    # times 1 assigned contract = $175.
    rows = [
        {
            "Date": "01/01/2026",
            "Action": "Sell to Open",
            "Symbol": "FOO 02/20/2026 10.00 P",
            "Quantity": "2",
            "Price": "$2.00",
            "Amount": "$400.00",
        },
        {
            "Date": "01/15/2026",
            "Action": "Buy to Close",
            "Symbol": "FOO 02/20/2026 10.00 P",
            "Quantity": "1",
            "Price": "$0.50",
            "Amount": "-$50.00",
        },
        {
            "Date": "02/20/2026",
            "Action": "Assigned",
            "Symbol": "FOO 02/20/2026 10.00 P",
            "Quantity": "1",
            "Price": "",
            "Amount": "",
        },
        {
            "Date": "02/20/2026",
            "Action": "Buy",
            "Symbol": "FOO",
            "Quantity": "100",
            "Price": "$10.00",
            "Amount": "-$1000.00",
        },
    ]
    trades = SchwabParser().parse(rows, account_display="schwab/st")
    foo_buy = next(t for t in trades if t.ticker == "FOO" and t.option_details is None)
    assert foo_buy.cost_basis == pytest.approx(825.0, abs=0.01)  # 1000 - 175
    assert foo_buy.basis_source == "put_assignment"


def test_normal_buy_unaffected_by_assignment_logic():
    rows = [
        {
            "Date": "06/15/2024",
            "Action": "Buy",
            "Symbol": "TSLA",
            "Quantity": "10",
            "Price": "$200.00",
            "Amount": "$-2000.00",
        }
    ]
    trades = SchwabParser().parse(rows, account_display="schwab/personal")
    assert trades[0].cost_basis == 2000.0
    assert trades[0].basis_source == "unknown"  # default — not adjusted
