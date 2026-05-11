from __future__ import annotations

from typer.testing import CliRunner

from net_alpha.cli.app import app

runner = CliRunner()


def test_backup_is_registered():
    result = runner.invoke(app, ["backup", "--help"])
    assert result.exit_code == 0
    assert "Create a backup bundle" in result.output


def test_restore_is_registered():
    result = runner.invoke(app, ["restore", "--help"])
    assert result.exit_code == 0
    assert "Restore" in result.output


def test_backups_group_is_registered():
    result = runner.invoke(app, ["backups", "--help"])
    assert result.exit_code == 0
    assert "ls" in result.output
    assert "rm" in result.output
    assert "prune" in result.output
