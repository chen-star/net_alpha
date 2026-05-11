"""Parser for the Schwab All-Positions CSV.

Schema:
  Line 1: '"Positions for All Accounts as of HH:MM AM/PM ET, YYYY/MM/DD"'
  Line 2: header row
  Line 3..N: data rows; final row(s) are summary "Account Total" rows we skip.

The single ``as_of_date`` from line 1 stamps every row in this import.
"""

from __future__ import annotations

import csv
import io
import re


class PositionsCSVParseError(ValueError):
    """Raised when a positions CSV cannot be parsed deterministically."""


_AS_OF_RE = re.compile(r"as of\s+[\d:]+\s*[APMapm]+\s*[A-Za-z]+,\s*(\d{4})/(\d{2})/(\d{2})")


def _parse_as_of(header_line: str) -> str:
    m = _AS_OF_RE.search(header_line)
    if not m:
        raise PositionsCSVParseError(
            "could not find as-of date in header line; "
            "expected 'Positions for All Accounts as of HH:MM AM/PM ET, YYYY/MM/DD'"
        )
    y, mo, d = m.group(1), m.group(2), m.group(3)
    return f"{y}-{mo}-{d}"


def _f(value: str | None) -> float:
    """Parse a numeric Schwab field. Handles '+17.00%', '$', commas, '--'."""
    if value is None or value.strip() in {"", "--", "N/A"}:
        return 0.0
    cleaned = value.replace("$", "").replace(",", "").replace("%", "").strip()
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    return float(cleaned)


def parse_positions_csv(content: str) -> tuple[list[dict], str]:
    """Parse the CSV content into row dicts + the single as_of_date.

    Returns:
      rows: list of {account_label, symbol, qty, cost_basis, market_value, unrealized_pl}
      as_of: 'YYYY-MM-DD'
    """
    lines = content.splitlines()
    if not lines:
        raise PositionsCSVParseError("empty CSV")
    as_of = _parse_as_of(lines[0])

    reader = csv.DictReader(io.StringIO("\n".join(lines[1:])))
    rows: list[dict] = []
    for raw in reader:
        symbol = (raw.get("Symbol") or "").strip()
        account = (raw.get("Account") or "").strip()
        if not symbol or account in {"", "Account Total"} or symbol == "Account Total":
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
