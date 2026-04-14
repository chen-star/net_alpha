from __future__ import annotations

import csv
import hashlib
from datetime import date, datetime
from pathlib import Path

from net_alpha.import_.option_parser import extract_underlying, parse_option_symbol
from net_alpha.import_.schema_detection import SchemaMapping
from net_alpha.models.domain import Trade


def read_csv_with_mapping(
    csv_path: Path,
    mapping: SchemaMapping,
    account: str,
    schema_cache_id: str,
) -> list[Trade]:
    """Read a broker CSV and produce Trade objects using the given schema mapping."""
    trades: list[Trade] = []

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_hash = _hash_row(row)
            trade = _row_to_trade(row, mapping, account, schema_cache_id, raw_hash)
            if trade is not None:
                trades.append(trade)

    return trades


def compute_header_hash(headers: list[str]) -> str:
    """SHA256 hash of the CSV header row for schema cache keying."""
    joined = ",".join(h.strip() for h in headers)
    return hashlib.sha256(joined.encode()).hexdigest()


def get_headers_and_samples(csv_path: Path, sample_count: int = 3) -> tuple[list[str], list[dict[str, str]]]:
    """Read CSV headers and up to sample_count sample rows."""
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        samples = []
        for i, row in enumerate(reader):
            if i >= sample_count:
                break
            samples.append(dict(row))
    return list(headers), samples


def _row_to_trade(
    row: dict[str, str],
    mapping: SchemaMapping,
    account: str,
    schema_cache_id: str,
    raw_hash: str,
) -> Trade | None:
    """Convert a CSV row to a Trade using the schema mapping."""
    raw_action = row.get(mapping.action, "").strip()

    # Determine canonical action
    if raw_action in mapping.buy_values:
        action = "Buy"
    elif raw_action in mapping.sell_values:
        action = "Sell"
    else:
        return None  # Skip rows that aren't buys or sells

    raw_date = row.get(mapping.date, "").strip()
    trade_date = _parse_date(raw_date)
    if trade_date is None:
        return None

    raw_symbol = row.get(mapping.ticker, "").strip()
    option_format = mapping.option_format

    # Parse option details if applicable
    option_details = None
    if option_format:
        option_details = parse_option_symbol(raw_symbol, option_format)

    # Extract underlying ticker
    ticker = extract_underlying(raw_symbol, option_format or "")

    quantity = _parse_float(row.get(mapping.quantity, ""))
    if quantity is None or quantity == 0:
        return None

    proceeds = _parse_float(row.get(mapping.proceeds, "")) if mapping.proceeds else None
    cost_basis = _parse_float(row.get(mapping.cost_basis, "")) if mapping.cost_basis else None
    basis_unknown = mapping.cost_basis is None or (mapping.cost_basis and not row.get(mapping.cost_basis, "").strip())

    return Trade(
        account=account,
        date=trade_date,
        ticker=ticker,
        action=action,
        quantity=quantity,
        proceeds=proceeds,
        cost_basis=cost_basis,
        basis_unknown=basis_unknown if mapping.cost_basis is None else False,
        option_details=option_details,
        raw_row_hash=raw_hash,
        schema_cache_id=schema_cache_id,
    )


def _parse_date(raw: str) -> date | None:
    """Parse a date string in common formats."""
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _parse_float(raw: str | None) -> float | None:
    """Parse a float from a CSV value, handling $, commas, parens."""
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    negative = raw.startswith("(") and raw.endswith(")")
    clean = raw.replace("$", "").replace(",", "").replace("(", "").replace(")", "")
    try:
        val = float(clean)
        return -val if negative else val
    except ValueError:
        return None


def _hash_row(row: dict[str, str]) -> str:
    """SHA256 hash of a raw CSV row for deduplication."""
    content = "|".join(f"{k}={v}" for k, v in sorted(row.items()))
    return hashlib.sha256(content.encode()).hexdigest()
