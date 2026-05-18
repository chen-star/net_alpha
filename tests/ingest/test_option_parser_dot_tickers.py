"""Option-symbol parser must accept tickers with a '.' (e.g. BRK.B, BF.B).

Regression for the I10 bug: the Schwab and Robinhood human-readable
regexes required ticker chars to be ``[A-Z][A-Z0-9]{0,5}`` — no dot.
A Schwab option string ``BRK.B 04/19/2024 400.00 C`` returned None,
and downstream the row landed in the trades table with a junk ticker
of the entire option-symbol string. The OCC standard strips the dot
on its own (``BRKB...``) so it's already correct.
"""

from __future__ import annotations

from datetime import date

import pytest

from net_alpha.ingest.option_parser import parse_option_symbol


def test_schwab_format_dot_ticker_brk_b():
    result = parse_option_symbol("BRK.B 04/19/2024 400.00 C")
    assert result is not None
    ticker, opt = result
    assert ticker == "BRK.B"
    assert opt.strike == 400.0
    assert opt.expiry == date(2024, 4, 19)
    assert opt.call_put == "C"


def test_schwab_format_dot_ticker_bf_b():
    result = parse_option_symbol("BF.B 12/20/2025 50.00 P")
    assert result is not None
    ticker, opt = result
    assert ticker == "BF.B"
    assert opt.strike == 50.0
    assert opt.call_put == "P"


def test_robinhood_format_dot_ticker():
    result = parse_option_symbol("BRK.B $400 Call 04/19/2024")
    assert result is not None
    ticker, opt = result
    assert ticker == "BRK.B"
    assert opt.strike == 400.0
    assert opt.call_put == "C"


@pytest.mark.parametrize(
    "symbol,expected_ticker",
    [
        ("TSLA 12/20/2024 250.00 C", "TSLA"),
        ("GME1 01/16/2026 30.00 C", "GME1"),
        ("AAPL 03/21/2025 175.00 P", "AAPL"),
    ],
)
def test_schwab_format_plain_tickers_still_work(symbol, expected_ticker):
    """Regression guard: the dot-allowing change must not break tickers
    without a dot."""
    result = parse_option_symbol(symbol)
    assert result is not None
    ticker, _ = result
    assert ticker == expected_ticker


def test_occ_format_dot_stripped_by_broker_still_works():
    """OCC: BRK.B is encoded as ``BRKB`` (5-char ticker, no dot)."""
    result = parse_option_symbol("BRKB240419C00400000")
    assert result is not None
    ticker, opt = result
    assert ticker == "BRKB"
    assert opt.strike == 400.0
