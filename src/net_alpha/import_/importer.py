from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from net_alpha.import_.anonymizer import anonymize_row
from net_alpha.import_.csv_reader import (
    compute_header_hash,
    get_headers_and_samples,
    read_csv_with_mapping,
)
from net_alpha.import_.dedup import deduplicate_trades
from net_alpha.import_.schema_detection import SchemaMapping, detect_schema


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
    anthropic_client: object  # Anthropic client instance
    model: str
    max_retries: int
    # Callbacks for user interaction (injected by CLI layer)
    confirm_schema: object  # Callable[[SchemaMapping, list[str]], bool]
    # Repository access
    trade_repo: object  # TradeRepository
    schema_cache_repo: object  # SchemaCacheRepository
    session: object  # SQLModel Session


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
        if not ctx.confirm_schema(mapping, headers):
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
