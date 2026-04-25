from __future__ import annotations

import re
from datetime import date

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


def _parse_occ(symbol: str) -> tuple[str, OptionDetails] | None:
    m = _OCC_PATTERN.match(symbol)
    if not m:
        return None
    ticker = m.group("ticker")
    details = OptionDetails(
        strike=int(m.group("strike")) / 1000.0,
        expiry=date(2000 + int(m.group("yy")), int(m.group("mm")), int(m.group("dd"))),
        call_put=m.group("cp"),
    )
    return ticker, details


def _parse_schwab(symbol: str) -> tuple[str, OptionDetails] | None:
    m = _SCHWAB_PATTERN.match(symbol)
    if not m:
        return None
    ticker = m.group("ticker")
    details = OptionDetails(
        strike=float(m.group("strike")),
        expiry=date(int(m.group("yyyy")), int(m.group("mm")), int(m.group("dd"))),
        call_put=m.group("cp"),
    )
    return ticker, details


def _parse_robinhood(symbol: str) -> tuple[str, OptionDetails] | None:
    m = _ROBINHOOD_PATTERN.match(symbol)
    if not m:
        return None
    ticker = m.group("ticker")
    cp = "C" if m.group("cp_word") == "Call" else "P"
    details = OptionDetails(
        strike=float(m.group("strike")),
        expiry=date(int(m.group("yyyy")), int(m.group("mm")), int(m.group("dd"))),
        call_put=cp,
    )
    return ticker, details


_PARSERS = [_parse_occ, _parse_schwab, _parse_robinhood]


def parse_option_symbol(symbol: str) -> tuple[str, OptionDetails] | None:
    """Parse an option symbol string into (underlying_ticker, OptionDetails).

    Tries OCC standard, Schwab human-readable, and Robinhood human-readable
    formats in order. Returns None if the symbol is not an option or cannot
    be parsed by any known format.
    """
    symbol = symbol.strip()
    for parser in _PARSERS:
        result = parser(symbol)
        if result is not None:
            return result
    return None
