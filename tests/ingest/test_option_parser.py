"""Regression tests for option-symbol parsing edge cases."""

from datetime import date

from net_alpha.ingest.option_parser import parse_option_symbol


def test_schwab_format_basic():
    result = parse_option_symbol("TSLA 12/20/2024 250.00 C")
    assert result is not None
    ticker, opt = result
    assert ticker == "TSLA"
    assert opt.strike == 250.0
    assert opt.expiry == date(2024, 12, 20)
    assert opt.call_put == "C"


def test_schwab_format_underlying_with_digit_suffix():
    """Corporate actions can produce tickers like 'GME1' (post stock dividend).
    Without this, the symbol fails to parse, the full string becomes the ticker,
    and downstream Yahoo split lookups 404 noisily."""
    result = parse_option_symbol("GME1 01/16/2026 30.00 C")
    assert result is not None
    ticker, opt = result
    assert ticker == "GME1"
    assert opt.strike == 30.0
    assert opt.call_put == "C"


def test_occ_format_underlying_with_digit_suffix():
    # GME1 + 260116 + C + 00030000 = GME1260116C00030000
    result = parse_option_symbol("GME1260116C00030000")
    assert result is not None
    ticker, opt = result
    assert ticker == "GME1"
    assert opt.strike == 30.0
    assert opt.call_put == "C"


def test_unparseable_returns_none():
    assert parse_option_symbol("TSLA") is None
    assert parse_option_symbol("not an option") is None
    assert parse_option_symbol("") is None
