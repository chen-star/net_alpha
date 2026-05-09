from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from net_alpha.cli import default
from net_alpha.cli.app import app
from net_alpha.db.repository import Repository

ROBINHOOD_FIXTURE = Path(__file__).parent.parent / "fixtures" / "robinhood_sample.csv"
SCHWAB_FIXTURE = Path(__file__).parent.parent / "fixtures" / "schwab_sample.csv"


def test_run_with_robinhood_csv_creates_robinhood_account(tmp_path, monkeypatch):
    """CLI default route creates a robinhood-broker account when given a Robinhood CSV."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [str(ROBINHOOD_FIXTURE), "--account", "personal"],
    )
    assert result.exit_code == 0, result.output
    repo = Repository(default._engine())
    accts = repo.list_accounts()
    assert any(a.broker == "robinhood" and a.label == "personal" for a in accts)


def test_run_with_mixed_broker_csvs_creates_separate_accounts(tmp_path, monkeypatch):
    """CLI default route creates separate accounts for Schwab and Robinhood CSVs."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [str(SCHWAB_FIXTURE), str(ROBINHOOD_FIXTURE), "--account", "personal"],
    )
    assert result.exit_code == 0, result.output
    repo = Repository(default._engine())
    brokers = {(a.broker, a.label) for a in repo.list_accounts()}
    assert ("schwab", "personal") in brokers
    assert ("robinhood", "personal") in brokers
