from datetime import date

from net_alpha.import_.option_parser import parse_option_symbol


def test_occ_standard_format():
    """OCC standard: TSLA241220C00250000"""
    result = parse_option_symbol("TSLA241220C00250000", "occ_standard")
    assert result is not None
    assert result.strike == 250.0
    assert result.expiry == date(2024, 12, 20)
    assert result.call_put == "C"


def test_occ_standard_put():
    result = parse_option_symbol("AAPL241115P00175000", "occ_standard")
    assert result is not None
    assert result.strike == 175.0
    assert result.call_put == "P"


def test_schwab_human_format():
    """Schwab human-readable: TSLA 12/20/2024 250.00 C"""
    result = parse_option_symbol("TSLA 12/20/2024 250.00 C", "schwab_human")
    assert result is not None
    assert result.strike == 250.0
    assert result.expiry == date(2024, 12, 20)
    assert result.call_put == "C"


def test_schwab_human_put():
    result = parse_option_symbol("NVDA 01/17/2025 500.00 P", "schwab_human")
    assert result is not None
    assert result.strike == 500.0
    assert result.expiry == date(2025, 1, 17)
    assert result.call_put == "P"


def test_robinhood_human_format():
    """Robinhood: TSLA $250 Call 12/20/2024"""
    result = parse_option_symbol("TSLA $250 Call 12/20/2024", "robinhood_human")
    assert result is not None
    assert result.strike == 250.0
    assert result.expiry == date(2024, 12, 20)
    assert result.call_put == "C"


def test_robinhood_human_put():
    result = parse_option_symbol("AAPL $175.50 Put 11/15/2024", "robinhood_human")
    assert result is not None
    assert result.strike == 175.5
    assert result.expiry == date(2024, 11, 15)
    assert result.call_put == "P"


def test_plain_equity_returns_none():
    """Plain ticker is not an option."""
    assert parse_option_symbol("TSLA", "occ_standard") is None
    assert parse_option_symbol("AAPL", "schwab_human") is None


def test_unknown_format_cascade():
    """Unknown format tries all parsers."""
    result = parse_option_symbol("TSLA241220C00250000", "unknown_format")
    assert result is not None
    assert result.strike == 250.0


def test_unparseable_returns_none():
    """Truly unparseable string."""
    result = parse_option_symbol("SOME RANDOM TEXT", "occ_standard")
    assert result is None


def test_extract_underlying_ticker():
    from net_alpha.import_.option_parser import extract_underlying

    assert extract_underlying("TSLA241220C00250000", "occ_standard") == "TSLA"
    assert extract_underlying("TSLA 12/20/2024 250.00 C", "schwab_human") == "TSLA"
    assert extract_underlying("TSLA $250 Call 12/20/2024", "robinhood_human") == "TSLA"
    assert extract_underlying("AAPL", "occ_standard") == "AAPL"
