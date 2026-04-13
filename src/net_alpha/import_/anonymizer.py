from __future__ import annotations

import re

# Matches standalone numbers with 4+ digits (account numbers)
_ACCOUNT_PATTERN = re.compile(r"^\d{4,}$|[-_]\d{4,}$|\d{4,}[-_]$|^\w*-\d{4,}$")

# Matches numeric values: optional $, optional negative, digits with commas, optional decimal
_NUMERIC_PATTERN = re.compile(r"^[($-]*[\d,]+\.?\d*[)]*$")

# Matches date patterns (YYYY-MM-DD, MM/DD/YYYY, etc.)
_DATE_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}$"  # 2024-10-15
    r"|^\d{1,2}/\d{1,2}/\d{2,4}$"  # 10/15/2024
    r"|^\w+ \d{1,2}, \d{4}$"  # October 15, 2024
)

# Matches ticker-like strings (1-5 uppercase letters, optionally with option suffix)
_TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}(\s|$)")


def anonymize_row(raw_row: dict[str, str]) -> dict[str, str]:
    """Anonymize a CSV row before sending to LLM.

    Rules:
    1. Numeric columns → replace with "1.00"
    2. Account number patterns (4+ digit sequences) → replace with "XXXX"
    3. Dates → kept as-is (structural signal, not PII)
    4. Ticker symbols → kept as-is (needed for LLM column identification)
    """
    result = {}
    for key, value in raw_row.items():
        result[key] = _anonymize_value(value)
    return result


def _anonymize_value(value: str) -> str:
    if not value or not value.strip():
        return value

    stripped = value.strip()

    # Preserve dates
    if _DATE_PATTERN.match(stripped):
        return value

    # Preserve ticker-like values (uppercase letters, option symbols)
    if _TICKER_PATTERN.match(stripped) and not stripped.isdigit():
        return value

    # Mask account numbers (4+ digit sequences)
    if _ACCOUNT_PATTERN.match(stripped):
        return "XXXX"

    # Replace numeric values
    clean = stripped.replace("$", "").replace(",", "").replace("(", "").replace(")", "")
    try:
        float(clean)
        return "1.00"
    except ValueError:
        pass

    return value
