"""Synthetic assigned-put close must land on the assignment date.

Regression for the I6 bug: after emitting the STO trade, the parser
reconstructed a Schwab symbol string with ``f"{strike:.2f}"`` formatting
and looked it up in ``assignment_dates``. If Schwab's actual symbol used
a different strike precision (mini options, oddball decimals) the lookup
missed and ``close_date`` silently fell back to ``t.date`` — the STO date
— making the short put look like it was opened and closed the same day.

The structured fix: key ``assignment_dates`` by
``(ticker, strike, expiry, call_put)`` so we don't depend on string
reformatting.
"""

from __future__ import annotations

import pytest

from net_alpha.brokers.schwab import SchwabParser


@pytest.mark.parametrize(
    "symbol,strike_text",
    [
        # Schwab can emit strike with varying decimal precision.
        ("FOO 02/20/2026 10.00 P", "10.00"),
        ("FOO 02/20/2026 10.0 P", "10.0"),
        ("FOO 02/20/2026 10 P", "10"),
    ],
)
def test_assigned_put_synthetic_close_lands_on_assignment_date(symbol, strike_text):
    """The synthetic ``option_short_close_assigned`` trade must use the
    Assigned row's date, regardless of strike formatting in the symbol."""
    rows = [
        {
            "Date": "01/05/2026",
            "Action": "Sell to Open",
            "Symbol": symbol,
            "Quantity": "1",
            "Price": "$2.00",
            "Amount": "$200.00",
        },
        {
            "Date": "02/20/2026",
            "Action": "Assigned",
            "Symbol": symbol,
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
    trades = SchwabParser().parse(rows, account_display="schwab/personal")

    close_trades = [t for t in trades if t.basis_source == "option_short_close_assigned"]
    assert len(close_trades) == 1
    assert close_trades[0].date.isoformat() == "2026-02-20"
