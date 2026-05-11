from __future__ import annotations

import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from net_alpha.cli.backup import backup_cmd, backups_app, restore_cmd

runner = CliRunner()


def _seed(home: Path) -> None:
    data = home / ".net_alpha"
    data.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(data / "net_alpha.db")
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO meta VALUES ('schema_version', '20')")
    con.commit()
    con.close()


def test_backup_cmd_creates_bundle(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed(tmp_path)
    import typer

    app = typer.Typer()
    app.command()(backup_cmd)
    result = runner.invoke(app, [])
    assert result.exit_code == 0, result.output
    assert "Created" in result.output
    backups = list((tmp_path / ".net_alpha" / "backups").glob("*.tar.gz"))
    assert len(backups) == 1


def test_backups_ls_lists_bundles(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed(tmp_path)
    import net_alpha.backup as backup

    backup.create_bundle(reason="manual")
    result = runner.invoke(backups_app, ["ls"])
    assert result.exit_code == 0, result.output
    assert "manual" in result.output


def test_backups_ls_json(tmp_path, monkeypatch):
    import json

    monkeypatch.setenv("HOME", str(tmp_path))
    _seed(tmp_path)
    import net_alpha.backup as backup

    backup.create_bundle(reason="manual")
    result = runner.invoke(backups_app, ["ls", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert len(parsed) == 1
    assert parsed[0]["reason"] == "manual"


def test_restore_dry_run(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed(tmp_path)
    monkeypatch.setattr("getpass.getpass", lambda *args, **kwargs: "")
    import typer

    import net_alpha.backup as backup

    bundle_path = backup.create_bundle(reason="manual")
    app = typer.Typer()
    app.command()(restore_cmd)
    result = runner.invoke(app, [str(bundle_path), "--dry-run"], input="\n")
    assert result.exit_code == 0, result.output
    assert "manual" in result.output
    # No .bak file from a dry-run.
    assert not list((tmp_path / ".net_alpha").glob("*.bak"))
