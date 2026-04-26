from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from net_alpha.cli.app import app

TX_FIXTURE = Path(__file__).parent.parent / "web" / "fixtures" / "schwab_minimal.csv"
GL_FIXTURE = Path(__file__).parent.parent / "brokers" / "fixtures" / "schwab_realized_gl_min.csv"


def test_cli_imports_both_files_with_account(tmp_path, monkeypatch):
    monkeypatch.setenv("NET_ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [str(TX_FIXTURE), str(GL_FIXTURE), "--account", "personal"],
    )
    assert result.exit_code == 0, result.output
    # The G/L lots from the fixture cover WRD and CRCL — the output should mention activity
    assert "Imported" in result.output or "G/L" in result.output


def test_cli_single_transactions_file_runs_fifo_stitch(tmp_path, monkeypatch):
    monkeypatch.setenv("NET_ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, [str(TX_FIXTURE), "--account", "personal"])
    assert result.exit_code == 0, result.output
