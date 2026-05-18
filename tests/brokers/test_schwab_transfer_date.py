"""Transfer-in rows must record the statement date as ``transfer_date``.

Regression for the I2 bug: the parser wrote the broker's transfer
statement date as ``Trade.date`` and left ``Trade.transfer_date=None``.
When the user later corrects the lot's acquisition date via the
set-basis editor (which writes the original acquisition date to
``Trade.date``), the transfer date is lost entirely.

This narrow fix preserves the broker's statement date in
``Trade.transfer_date`` so it stays available alongside the eventual
user-set acquisition date. Holding-period math (§1223(3)) still needs
the user to enter the original acquisition date for an accurate LT/ST
classification — that's the design constraint of the broker data, not
a parser bug.
"""

from __future__ import annotations

from net_alpha.brokers.schwab import SchwabParser


def test_security_transfer_in_populates_transfer_date():
    rows = [
        {
            "Date": "03/05/2026",
            "Action": "Security Transfer",
            "Symbol": "AAPL",
            "Quantity": "100",
            "Price": "",
            "Amount": "",
        }
    ]
    trades = SchwabParser().parse(rows, account_display="schwab/lt")
    assert len(trades) == 1
    t = trades[0]
    assert t.basis_source == "transfer_in"
    assert t.action == "Buy"
    # Broker statement date is stored as transfer_date so it persists when
    # the user later overrides ``Trade.date`` with the original acquisition
    # date via the basis editor.
    assert t.transfer_date is not None
    assert t.transfer_date.isoformat() == "2026-03-05"


def test_journaled_shares_in_populates_transfer_date():
    rows = [
        {
            "Date": "03/05/2026",
            "Action": "Journaled Shares",
            "Symbol": "TSLA",
            "Quantity": "10",
            "Price": "$200.00",
            "Amount": "",
        }
    ]
    trades = SchwabParser().parse(rows, account_display="schwab/lt")
    assert len(trades) == 1
    assert trades[0].transfer_date is not None
    assert trades[0].transfer_date.isoformat() == "2026-03-05"


def test_transfer_out_does_not_populate_transfer_date():
    """Transfer-OUT is a disposal; ``transfer_date`` only meaningful for inbound."""
    rows = [
        {
            "Date": "03/05/2026",
            "Action": "Security Transfer",
            "Symbol": "AAPL",
            "Quantity": "-100",
            "Price": "",
            "Amount": "",
        }
    ]
    trades = SchwabParser().parse(rows, account_display="schwab/lt")
    assert len(trades) == 1
    assert trades[0].basis_source == "transfer_out"
    # No semantic need to populate transfer_date on the Sell side — the lot
    # being disposed of already has its own acquisition history.
    assert trades[0].transfer_date is None


def test_regular_buy_does_not_populate_transfer_date():
    """Sanity: an ordinary equity Buy must not get transfer_date populated."""
    rows = [
        {
            "Date": "08/01/2024",
            "Action": "Buy",
            "Symbol": "TSLA",
            "Quantity": "10",
            "Price": "$200.00",
            "Amount": "-$2000.00",
        }
    ]
    trades = SchwabParser().parse(rows, account_display="schwab/personal")
    assert len(trades) == 1
    assert trades[0].transfer_date is None
