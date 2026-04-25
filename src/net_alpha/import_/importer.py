from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from net_alpha.import_.csv_reader import (
    SchemaMapping,
    compute_header_hash,
    get_headers_and_samples,
    read_csv_with_mapping,
)
from net_alpha.import_.dedup import deduplicate_trades

# ---------------------------------------------------------------------------
# Anonymizer (inlined from deleted anonymizer.py)
# ---------------------------------------------------------------------------

_ACCOUNT_PATTERN = re.compile(r"^\d{4,}$|[-_]\d{4,}$|\d{4,}[-_]$|^\w*-\d{4,}$")
_DATE_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}$"
    r"|^\d{1,2}/\d{1,2}/\d{2,4}$"
    r"|^\w+ \d{1,2}, \d{4}$"
)
_TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}(\s|$)")


def _anonymize_value(value: str) -> str:
    if not value or not value.strip():
        return value
    stripped = value.strip()
    if _DATE_PATTERN.match(stripped):
        return value
    if _TICKER_PATTERN.match(stripped) and not stripped.isdigit():
        return value
    if _ACCOUNT_PATTERN.match(stripped):
        return "XXXX"
    clean = stripped.replace("$", "").replace(",", "").replace("(", "").replace(")", "")
    try:
        float(clean)
        return "1.00"
    except ValueError:
        pass
    return value


def anonymize_row(raw_row: dict[str, str]) -> dict[str, str]:
    return {key: _anonymize_value(value) for key, value in raw_row.items()}


# ---------------------------------------------------------------------------
# Schema detection (inlined from deleted schema_detection.py)
# ---------------------------------------------------------------------------

KNOWN_BROKER_SCHEMAS: dict[str, SchemaMapping] = {
    "schwab": SchemaMapping(
        date="Date",
        ticker="Symbol",
        action="Action",
        quantity="Quantity",
        proceeds="Amount",
        cost_basis="Cost Basis",
        buy_values=["Buy", "Reinvest"],
        sell_values=["Sell"],
        option_format="schwab_human",
    ),
    "robinhood": SchemaMapping(
        date="Activity Date",
        ticker="Instrument",
        action="Trans Code",
        quantity="Quantity",
        proceeds="Amount",
        cost_basis=None,
        buy_values=["Buy"],
        sell_values=["Sell"],
        option_format="robinhood_human",
    ),
}


def detect_schema(
    client,
    headers: list[str],
    sample_rows: list[dict[str, str]],
    model: str,
    max_retries: int = 3,
) -> SchemaMapping:
    """Call LLM to detect CSV schema from headers and anonymized sample rows."""
    import json as _json
    import time

    prompt = _build_schema_prompt(headers, sample_rows)
    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            if text.startswith("```"):
                lines = [line for line in text.split("\n") if not line.strip().startswith("```")]
                text = "\n".join(lines).strip()
            data = _json.loads(text)
            return SchemaMapping(**data)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
    raise RuntimeError(f"Schema detection failed after {max_retries} attempts. Last error: {last_error}")


def _build_schema_prompt(headers: list[str], sample_rows: list[dict[str, str]]) -> str:
    header_str = ", ".join(headers)
    rows_str = "\n".join(", ".join(f"{k}: {v}" for k, v in row.items()) for row in sample_rows)
    return f"""Analyze this broker CSV format and return a JSON mapping.

CSV Headers: {header_str}

Sample rows (anonymized):
{rows_str}

Return a JSON object with these fields:
- "date": column name containing trade date
- "ticker": column name containing ticker/symbol
- "action": column name containing buy/sell action
- "quantity": column name containing quantity/shares
- "proceeds": column name containing sale proceeds or total amount (null if not present)
- "cost_basis": column name containing cost basis (null if not present)
- "buy_values": list of values in the action column that mean "buy"
- "sell_values": list of values in the action column that mean "sell"
- "option_format": if options are present: "occ_standard", "schwab_human", or "robinhood_human" (null if none)

Return ONLY the JSON object, no other text."""


@dataclass
class ImportResult:
    total_parsed: int
    new_imported: int
    duplicates_skipped: int
    equities: int
    options: int
    etfs: int  # Count is approximate — based on known ETF tickers, or 0


@dataclass
class ImportContext:
    """Everything the import orchestrator needs to run."""

    csv_path: Path
    broker_name: str
    anthropic_client: object | None  # Anthropic client instance
    model: str
    max_retries: int
    # Callbacks for user interaction (injected by CLI layer)
    confirm_schema: object  # Callable[[SchemaMapping, list[str]], bool]
    # Repository access
    trade_repo: object  # TradeRepository
    schema_cache_repo: object  # SchemaCacheRepository
    session: object  # SQLModel Session


def _extract_examples(mapping: SchemaMapping, sample_rows: list[dict]) -> dict[str, str]:
    """Extract first non-empty value per mapped column from sample rows."""
    fields = {
        "date": mapping.date,
        "ticker": mapping.ticker,
        "action": mapping.action,
        "quantity": mapping.quantity,
    }
    if mapping.proceeds:
        fields["proceeds"] = mapping.proceeds
    if mapping.cost_basis:
        fields["cost_basis"] = mapping.cost_basis

    examples: dict[str, str] = {}
    for field_name, col_name in fields.items():
        for row in sample_rows:
            val = str(row.get(col_name, "")).strip()
            if val:
                examples[field_name] = val
                break
    return examples


def run_import(ctx: ImportContext) -> ImportResult:
    """Run the full import pipeline.

    1. Read headers + samples
    2. Check schema cache → if miss, call LLM + confirm
    3. Parse all rows
    4. Deduplicate
    5. Persist
    """
    headers, raw_samples = get_headers_and_samples(ctx.csv_path)
    header_hash = compute_header_hash(headers)

    # Check schema cache
    cached = ctx.schema_cache_repo.find_by_broker_and_hash(ctx.broker_name, header_hash)
    if cached is not None:
        mapping = SchemaMapping(**json.loads(cached.column_mapping))
        schema_cache_id = cached.id
    else:
        if ctx.broker_name in KNOWN_BROKER_SCHEMAS:
            mapping = KNOWN_BROKER_SCHEMAS[ctx.broker_name]
            schema_cache_id = None
        else:
            if not ctx.anthropic_client:
                raise RuntimeError(
                    f"We don't have a built-in schema for '{ctx.broker_name}'. "
                    "To import this file, you must set an ANTHROPIC_API_KEY so the AI can analyze it."
                )

            # Anonymize samples before LLM call
            anon_samples = [anonymize_row(row) for row in raw_samples]

            # LLM schema detection
            mapping = detect_schema(
                client=ctx.anthropic_client,
                headers=headers,
                sample_rows=anon_samples,
                model=ctx.model,
                max_retries=ctx.max_retries,
            )

            # User confirmation
            examples = _extract_examples(mapping, raw_samples)
            if not ctx.confirm_schema(mapping, headers, examples):
                raise RuntimeError("Schema rejected by user. Import cancelled.")

            # Cache the confirmed schema
            from net_alpha.db.tables import SchemaCacheRow

            schema_cache_id = str(uuid4())
            cache_row = SchemaCacheRow(
                id=schema_cache_id,
                broker_name=ctx.broker_name,
                header_hash=header_hash,
                column_mapping=mapping.model_dump_json(),
                option_format=mapping.option_format,
            )
            ctx.schema_cache_repo.save(cache_row)
            ctx.session.commit()

    # Parse all CSV rows
    trades = read_csv_with_mapping(
        csv_path=ctx.csv_path,
        mapping=mapping,
        account=ctx.broker_name,
        schema_cache_id=schema_cache_id,
    )

    # Deduplicate
    new_trades, skipped = deduplicate_trades(trades, ctx.trade_repo)

    # Persist
    ctx.trade_repo.save_batch(new_trades)
    ctx.session.commit()

    # Count types
    options_count = sum(1 for t in new_trades if t.is_option())
    equities_count = len(new_trades) - options_count

    return ImportResult(
        total_parsed=len(trades),
        new_imported=len(new_trades),
        duplicates_skipped=skipped,
        equities=equities_count,
        options=options_count,
        etfs=0,  # ETF classification requires ETF pairs list; CLI layer handles display
    )
