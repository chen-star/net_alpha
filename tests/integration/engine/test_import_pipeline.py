"""Integration tests: CSV import pipeline with real temp DB."""
from __future__ import annotations

import json
from pathlib import Path

from net_alpha.db.repository import SchemaCacheRepository, TradeRepository
from net_alpha.import_.csv_reader import compute_header_hash, get_headers_and_samples
from net_alpha.import_.importer import ImportContext, run_import
from tests.integration.conftest import (
    ROBINHOOD_MAPPING,
    SCHWAB_MAPPING,
    make_llm_response,
)


def _ctx(session, csv_path: Path, broker: str, mock_client) -> ImportContext:
    """Build a minimal ImportContext for engine-level import tests."""
    return ImportContext(
        csv_path=csv_path,
        broker_name=broker,
        anthropic_client=mock_client,
        model="claude-haiku-4-5",
        max_retries=1,
        confirm_schema=lambda mapping, headers: True,  # auto-confirm
        trade_repo=TradeRepository(session),
        schema_cache_repo=SchemaCacheRepository(session),
        session=session,
    )


# ---------------------------------------------------------------------------
# Schwab pipeline
# ---------------------------------------------------------------------------

def test_schwab_full_pipeline(temp_db, schwab_csv, mock_anthropic_client):
    """CSV import: 4 Trade rows written; option trade parsed correctly."""
    engine, session, _ = temp_db
    mock_anthropic_client.messages.create.return_value = make_llm_response(SCHWAB_MAPPING)

    result = run_import(_ctx(session, schwab_csv, "schwab", mock_anthropic_client))

    assert result.new_imported == 4
    assert result.duplicates_skipped == 0

    trades = TradeRepository(session).list_all()
    assert len(trades) == 4

    option_trade = next(t for t in trades if t.option_details is not None)
    assert option_trade.ticker == "TSLA"
    assert option_trade.option_details.call_put == "C"
    assert option_trade.option_details.strike == 250.0


# ---------------------------------------------------------------------------
# Robinhood pipeline
# ---------------------------------------------------------------------------

def test_robinhood_full_pipeline(temp_db, robinhood_csv, mock_anthropic_client):
    """CSV import: 4 trades written; robinhood_human option format cached."""
    engine, session, _ = temp_db
    mock_anthropic_client.messages.create.return_value = make_llm_response(ROBINHOOD_MAPPING)

    result = run_import(_ctx(session, robinhood_csv, "robinhood", mock_anthropic_client))

    assert result.new_imported == 4

    headers, _ = get_headers_and_samples(robinhood_csv)
    hash_ = compute_header_hash(headers)
    cached = SchemaCacheRepository(session).find_by_broker_and_hash("robinhood", hash_)
    assert cached is not None
    assert cached.option_format == "robinhood_human"


# ---------------------------------------------------------------------------
# Schema cache
# ---------------------------------------------------------------------------

def test_schema_cache_written_after_first_import(temp_db, schwab_csv, mock_anthropic_client):
    """Schema cache row written after first import."""
    engine, session, _ = temp_db
    mock_anthropic_client.messages.create.return_value = make_llm_response(SCHWAB_MAPPING)

    run_import(_ctx(session, schwab_csv, "schwab", mock_anthropic_client))

    headers, _ = get_headers_and_samples(schwab_csv)
    hash_ = compute_header_hash(headers)
    cached = SchemaCacheRepository(session).find_by_broker_and_hash("schwab", hash_)
    assert cached is not None
    assert json.loads(cached.column_mapping)["ticker"] == "Symbol"


def test_schema_cache_hit_skips_llm(temp_db, schwab_csv, mock_anthropic_client):
    """Second import of same broker+headers reads from cache; LLM called only once."""
    engine, session, _ = temp_db
    mock_anthropic_client.messages.create.return_value = make_llm_response(SCHWAB_MAPPING)

    run_import(_ctx(session, schwab_csv, "schwab", mock_anthropic_client))  # LLM called
    run_import(_ctx(session, schwab_csv, "schwab", mock_anthropic_client))  # cache hit

    assert mock_anthropic_client.messages.create.call_count == 1


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def test_dedup_hash_match(temp_db, schwab_csv, mock_anthropic_client):
    """Importing same CSV twice: second run reports 0 new, 4 skipped."""
    engine, session, _ = temp_db
    mock_anthropic_client.messages.create.return_value = make_llm_response(SCHWAB_MAPPING)

    first = run_import(_ctx(session, schwab_csv, "schwab", mock_anthropic_client))
    second = run_import(_ctx(session, schwab_csv, "schwab", mock_anthropic_client))

    assert first.new_imported == 4
    assert second.new_imported == 0
    assert second.duplicates_skipped == 4
    assert len(TradeRepository(session).list_all()) == 4


def test_cross_account_no_dedup(temp_db, schwab_csv, robinhood_csv, mock_anthropic_client):
    """Same ticker+date from different brokers: both stored (8 total)."""
    engine, session, _ = temp_db

    mock_anthropic_client.messages.create.return_value = make_llm_response(SCHWAB_MAPPING)
    run_import(_ctx(session, schwab_csv, "schwab", mock_anthropic_client))

    mock_anthropic_client.messages.create.return_value = make_llm_response(ROBINHOOD_MAPPING)
    run_import(_ctx(session, robinhood_csv, "robinhood", mock_anthropic_client))

    trades = TradeRepository(session).list_all()
    accounts = {t.account for t in trades}
    assert len(trades) == 8
    assert "schwab" in accounts
    assert "robinhood" in accounts
