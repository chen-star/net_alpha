"""Smoke test for `net-alpha straddles` — confirms the command is wired up
and surfaces a rendered output. Detection logic itself is covered by the
unit tests in tests/section_1092/."""

from typer.testing import CliRunner

from net_alpha.cli.app import app


def test_straddles_command_runs_with_no_data(tmp_path, monkeypatch):
    # Point net-alpha at an isolated home dir so an empty DB is initialised.
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(app, ["straddles"])
    assert result.exit_code == 0
    assert "1092" in result.stdout or "straddle" in result.stdout.lower()


def test_straddles_command_accepts_detail_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(app, ["straddles", "--detail"])
    assert result.exit_code == 0
