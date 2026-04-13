from __future__ import annotations

import re
from datetime import date
from typing import Optional

from net_alpha.models.domain import OptionDetails

# OCC standard: TSLA241220C00250000
# Ticker (1-6 chars) + YYMMDD + C/P + strike * 1000 (8 digits, zero-padded)
_OCC_PATTERN = re.compile(
    r"^(?P<ticker>[A-Z]{1,6})"
    r"(?P<yy>\d{2})(?P<mm>\d{2})(?P<dd>\d{2})"
    r"(?P<cp>[CP])"
    r"(?P<strike>\d{8})$"
)

# Schwab human-readable: TSLA 12/20/2024 250.00 C
_SCHWAB_PATTERN = re.compile(
    r"^(?P<ticker>[A-Z]{1,6})\s+"
    r"(?P<mm>\d{1,2})/(?P<dd>\d{1,2})/(?P<yyyy>\d{4})\s+"
    r"(?P<strike>[\d.]+)\s+"
    r"(?P<cp>[CP])$"
)

# Robinhood human-readable: TSLA $250 Call 12/20/2024
_ROBINHOOD_PATTERN = re.compile(
    r"^(?P<ticker>[A-Z]{1,6})\s+"
    r"\$(?P<strike>[\d.]+)\s+"
    r"(?P<cp_word>Call|Put)\s+"
    r"(?P<mm>\d{1,2})/(?P<dd>\d{1,2})/(?P<yyyy>\d{4})$"
)


def _parse_occ(symbol: str) -> Optional[OptionDetails]:
    m = _OCC_PATTERN.match(symbol)
    if not m:
        return None
    return OptionDetails(
        strike=int(m.group("strike")) / 1000.0,
        expiry=date(2000 + int(m.group("yy")), int(m.group("mm")), int(m.group("dd"))),
        call_put=m.group("cp"),
    )


def _parse_schwab(symbol: str) -> Optional[OptionDetails]:
    m = _SCHWAB_PATTERN.match(symbol)
    if not m:
        return None
    return OptionDetails(
        strike=float(m.group("strike")),
        expiry=date(int(m.group("yyyy")), int(m.group("mm")), int(m.group("dd"))),
        call_put=m.group("cp"),
    )


def _parse_robinhood(symbol: str) -> Optional[OptionDetails]:
    m = _ROBINHOOD_PATTERN.match(symbol)
    if not m:
        return None
    cp = "C" if m.group("cp_word") == "Call" else "P"
    return OptionDetails(
        strike=float(m.group("strike")),
        expiry=date(int(m.group("yyyy")), int(m.group("mm")), int(m.group("dd"))),
        call_put=cp,
    )


_PARSERS = {
    "occ_standard": _parse_occ,
    "schwab_human": _parse_schwab,
    "robinhood_human": _parse_robinhood,
}


def parse_option_symbol(
    symbol: str, option_format: str
) -> Optional[OptionDetails]:
    """Parse an option symbol string into OptionDetails.

    Uses the specified format's regex. Unknown formats try all parsers.
    Returns None if the symbol is not an option or cannot be parsed.
    """
    symbol = symbol.strip()

    if option_format in _PARSERS:
        result = _PARSERS[option_format](symbol)
        if result is not None:
            return result
        # If specified parser fails, don't cascade — only cascade for unknown
        if option_format != "unknown_format":
            return None

    # Best-effort cascade for unknown formats
    for parser in [_parse_occ, _parse_schwab, _parse_robinhood]:
        result = parser(symbol)
        if result is not None:
            return result

    return None


def extract_underlying(symbol: str, option_format: str) -> str:
    """Extract the underlying ticker from a symbol string.

    For options, extracts the underlying ticker (e.g., "TSLA" from "TSLA241220C00250000").
    For plain equities, returns the symbol as-is.
    """
    symbol = symbol.strip()

    # Try OCC format
    m = _OCC_PATTERN.match(symbol)
    if m:
        return m.group("ticker")

    # Try Schwab format
    m = _SCHWAB_PATTERN.match(symbol)
    if m:
        return m.group("ticker")

    # Try Robinhood format
    m = _ROBINHOOD_PATTERN.match(symbol)
    if m:
        return m.group("ticker")

    # Plain equity ticker
    return symbol.split()[0] if " " in symbol else symbol
