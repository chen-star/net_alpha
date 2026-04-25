from __future__ import annotations

import csv
import hashlib


def load_csv(path: str) -> tuple[list[str], list[dict[str, str]]]:
    """Read a CSV from disk. Returns (headers, rows)."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        rows = list(reader)
    return headers, rows


def compute_csv_sha256(path: str) -> str:
    """SHA256 of file contents — used for ImportRecord.csv_sha256 (informational)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
