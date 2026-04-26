from __future__ import annotations

import csv
import hashlib
import re

_DATE_PATTERN = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$|^\d{4}-\d{1,2}-\d{1,2}$")
_HEADER_SCAN_LIMIT = 5


def _looks_like_headers(row: list[str]) -> bool:
    """Heuristic: a row is the header row if it has 4+ non-empty cells AND
    no cell starts with '$' or matches a date pattern."""
    non_empty = [c.strip() for c in row if c.strip()]
    if len(non_empty) < 4:
        return False
    for cell in non_empty:
        if cell.startswith("$"):
            return False
        if _DATE_PATTERN.match(cell):
            return False
    return True


def _find_header_index(rows: list[list[str]]) -> int:
    for i in range(min(_HEADER_SCAN_LIMIT, len(rows))):
        if _looks_like_headers(rows[i]):
            return i
    return 0  # Fallback: assume first row is headers (legacy behavior)


def load_csv(path: str) -> tuple[list[str], list[dict[str, str]]]:
    """Read a CSV from disk. Returns (headers, rows).

    Skips up to 5 leading preamble rows (title rows, blank rows) before the
    real header row. Falls back to row 0 if no plausible header row is found.
    """
    with open(path, newline="", encoding="utf-8-sig") as f:
        all_rows = list(csv.reader(f))

    if not all_rows:
        return [], []

    header_idx = _find_header_index(all_rows)
    headers = [c.strip() for c in all_rows[header_idx]]
    data_rows: list[dict[str, str]] = []
    for raw in all_rows[header_idx + 1 :]:
        if not any(c.strip() for c in raw):
            continue  # skip blank rows
        # Pad short rows; truncate long rows
        padded = list(raw) + [""] * max(0, len(headers) - len(raw))
        data_rows.append({h: padded[i] for i, h in enumerate(headers)})
    return headers, data_rows


def compute_csv_sha256(path: str) -> str:
    """SHA256 of file contents — used for ImportRecord.csv_sha256 (informational)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
