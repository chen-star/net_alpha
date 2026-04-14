"""CLI integration tests: net-alpha import command."""
from __future__ import annotations

from unittest.mock import MagicMock

from sqlmodel import Session

from net_alpha.cli.app import app
from net_alpha.db.repository import TradeRepository
from tests.integration.conftest import (
    ROBINHOOD_MAPPING,
    SCHWAB_MAPPING,
    make_llm_response,
)

DISCLAIMER = "Consult a tax professional"


def _patch_import(monkeypatch, mock_client: MagicMock):
    """
    Patch the Anthropic class used by import_cmd so no real API calls are made.
    Also patch questionary.confirm so the schema confirmation returns True without
    waiting for stdin (CliRunner stdin injection is unreliable with questionary).

    Both imports happen inside function bodies in import_cmd.py, so we patch at
    the source module level rather than the import_cmd namespace.
    """
    monkeypatch.setattr("anthropic.Anthropic", lambda **kwargs: mock_client)

    mock_confirm = MagicMock()
    mock_confirm.return_value.ask.return_value = True
    monkeypatch.setattr("questionary.confirm", mock_confirm)


def test_schwab_import_llm_path(cli_setup, schwab_csv, monkeypatch):
    """Fresh DB, no cache: LLM called once, 4 trades imported, disclaimer shown."""
    runner, engine, _ = cli_setup
    mock_client = MagicMock()
    mock_client.messages.create.return_value = make_llm_response(SCHWAB_MAPPING)
    _patch_import(monkeypatch, mock_client)

    result = runner.invoke(app, ["import", "Schwab", str(schwab_csv)])

    assert result.exit_code == 0, result.output
    assert "4" in result.output
    assert DISCLAIMER in result.output
    assert mock_client.messages.create.call_count == 1

    with Session(engine) as s:
        assert len(TradeRepository(s).list_all()) == 4


def test_schwab_import_cache_hit(cli_setup, schwab_csv, monkeypatch):
    """Second import uses schema cache; LLM called only once total."""
    runner, engine, _ = cli_setup
    mock_client = MagicMock()
    mock_client.messages.create.return_value = make_llm_response(SCHWAB_MAPPING)
    _patch_import(monkeypatch, mock_client)

    runner.invoke(app, ["import", "Schwab", str(schwab_csv)])  # first: LLM called
    result = runner.invoke(app, ["import", "Schwab", str(schwab_csv)])  # second: cache hit

    assert result.exit_code == 0, result.output
    assert mock_client.messages.create.call_count == 1


def test_robinhood_import_llm_path(cli_setup, robinhood_csv, monkeypatch):
    """Robinhood CSV: LLM called, 4 trades imported, disclaimer shown."""
    runner, engine, _ = cli_setup
    mock_client = MagicMock()
    mock_client.messages.create.return_value = make_llm_response(ROBINHOOD_MAPPING)
    _patch_import(monkeypatch, mock_client)

    result = runner.invoke(app, ["import", "Robinhood", str(robinhood_csv)])

    assert result.exit_code == 0, result.output
    assert "4" in result.output
    assert DISCLAIMER in result.output


def test_duplicate_import_skips(cli_setup, schwab_csv, monkeypatch):
    """Import same CSV twice: second run shows duplicates skipped."""
    runner, engine, _ = cli_setup
    mock_client = MagicMock()
    mock_client.messages.create.return_value = make_llm_response(SCHWAB_MAPPING)
    _patch_import(monkeypatch, mock_client)

    runner.invoke(app, ["import", "Schwab", str(schwab_csv)])
    result = runner.invoke(app, ["import", "Schwab", str(schwab_csv)])

    assert result.exit_code == 0, result.output
    # Second run: new_imported=0, duplicates_skipped=4
    assert "duplicate" in result.output.lower() or "skipped" in result.output.lower()


def test_cross_account_same_ticker(cli_setup, schwab_csv, robinhood_csv, monkeypatch):
    """Schwab + Robinhood imports: DB holds 8 total trades across 2 accounts."""
    runner, engine, _ = cli_setup
    mock_client = MagicMock()
    _patch_import(monkeypatch, mock_client)

    mock_client.messages.create.return_value = make_llm_response(SCHWAB_MAPPING)
    r1 = runner.invoke(app, ["import", "Schwab", str(schwab_csv)])
    assert r1.exit_code == 0, r1.output

    mock_client.messages.create.return_value = make_llm_response(ROBINHOOD_MAPPING)
    r2 = runner.invoke(app, ["import", "Robinhood", str(robinhood_csv)])
    assert r2.exit_code == 0, r2.output

    with Session(engine) as s:
        trades = TradeRepository(s).list_all()
        accounts = {t.account for t in trades}
        assert len(trades) == 8
        assert "schwab" in accounts
        assert "robinhood" in accounts
