"""Parser for Schwab positions CSVs.

Two supported header shapes (line 1):

  All-Accounts:
    "Positions for All Accounts as of HH:MM AM/PM ET, YYYY/MM/DD"
    — has an "Account" column per row

  Per-Account:
    "Positions for account <LABEL> as of HH:MM AM/PM ET, YYYY/MM/DD"
    — account is in the header line; rows lack an Account column

Both paths produce row dicts of the same shape so the downstream verify
pipeline is format-agnostic.
"""

from __future__ import annotations

import csv
import io
import re


class PositionsCSVParseError(ValueError):
    """Raised when a positions CSV cannot be parsed deterministically."""


_AS_OF_ALL_RE = re.compile(
    r"Positions for All Accounts as of\s+[\d:]+\s*[APMapm]+\s*[A-Za-z]+,\s*"
    r"(\d{4})/(\d{2})/(\d{2})"
)

_AS_OF_ACCT_RE = re.compile(
    r"Positions for account\s+(?P<acct>.+?)\s+as of\s+[\d:]+\s*[APMapm]+\s*[A-Za-z]+,\s*"
    r"(?P<y>\d{4})/(?P<m>\d{2})/(?P<d>\d{2})"
)

# Symbols emitted by the per-account file that are not real holdings.
_NON_HOLDING_SYMBOLS = {
    "Cash & Cash Investments",
    "Futures Cash",
    "Futures Positions Market Value",
    "Positions Total",
    "Account Total",
}


def _f(value: str | None) -> float:
    """Parse a numeric Schwab field. Handles '+17.00%', '$', commas, '--'."""
    if value is None or value.strip() in {"", "--", "N/A"}:
        return 0.0
    cleaned = value.replace("$", "").replace(",", "").replace("%", "").strip()
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    return float(cleaned)


def _is_option_symbol(symbol: str) -> bool:
    """Schwab option symbols always contain a space-delimited expiry."""
    return " " in symbol.strip()


def parse_positions_csv(content: str) -> tuple[list[dict], str]:
    """Parse the CSV content into row dicts + the single as_of_date.

    Returns:
      rows: list of {account_label, symbol, qty, cost_basis, market_value, unrealized_pl}
      as_of: 'YYYY-MM-DD'
    """
    lines = content.splitlines()
    if not lines:
        raise PositionsCSVParseError("empty CSV")

    header = lines[0]
    if _AS_OF_ALL_RE.search(header):
        return _parse_all_accounts(header, lines[1:])
    m = _AS_OF_ACCT_RE.search(header)
    if m:
        return _parse_per_account(m, lines[1:])

    raise PositionsCSVParseError(
        "could not find as-of date in header line; expected either "
        "'Positions for All Accounts as of HH:MM AM/PM ET, YYYY/MM/DD' or "
        "'Positions for account <LABEL> as of HH:MM AM/PM ET, YYYY/MM/DD'"
    )


def _parse_all_accounts(header: str, body_lines: list[str]) -> tuple[list[dict], str]:
    m = _AS_OF_ALL_RE.search(header)
    assert m is not None  # caller already matched
    y, mo, d = m.group(1), m.group(2), m.group(3)
    as_of = f"{y}-{mo}-{d}"

    reader = csv.DictReader(io.StringIO("\n".join(body_lines)))
    rows: list[dict] = []
    for raw in reader:
        symbol = (raw.get("Symbol") or "").strip()
        account = (raw.get("Account") or "").strip()
        if not symbol or symbol in _NON_HOLDING_SYMBOLS or account in {"", "Account Total"}:
            continue
        if _is_option_symbol(symbol):
            continue
        rows.append(
            {
                "account_label": account,
                "symbol": symbol,
                "qty": _f(raw.get("Quantity", "0")),
                "cost_basis": _f(raw.get("Cost Basis", "0")),
                "market_value": _f(raw.get("Market Value", "0")),
                "unrealized_pl": _f(raw.get("Gain $", "0")),
            }
        )
    return rows, as_of


def _parse_per_account(match: re.Match[str], body_lines: list[str]) -> tuple[list[dict], str]:
    account = match.group("acct").strip()
    as_of = f"{match.group('y')}-{match.group('m')}-{match.group('d')}"

    # Drop any blank lines between header and column row.
    while body_lines and not body_lines[0].strip():
        body_lines = body_lines[1:]

    reader = csv.DictReader(io.StringIO("\n".join(body_lines)))
    rows: list[dict] = []
    for raw in reader:
        symbol = (raw.get("Symbol") or "").strip()
        if not symbol or symbol in _NON_HOLDING_SYMBOLS:
            continue
        if _is_option_symbol(symbol):
            continue
        rows.append(
            {
                "account_label": account,
                "symbol": symbol,
                "qty": _f(raw.get("Qty (Quantity)", "0")),
                "cost_basis": _f(raw.get("Cost Basis", "0")),
                "market_value": _f(raw.get("Mkt Val (Market Value)", "0")),
                "unrealized_pl": _f(raw.get("Gain $ (Gain/Loss $)", "0")),
            }
        )
    return rows, as_of
