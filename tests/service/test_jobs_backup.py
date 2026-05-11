from __future__ import annotations

import sqlite3

from net_alpha.service.jobs.backup import run_backup_job


def test_run_backup_job_creates_daily_bundle(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    data = tmp_path / ".net_alpha"
    data.mkdir()
    con = sqlite3.connect(data / "net_alpha.db")
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO meta VALUES ('schema_version', '20')")
    con.commit()
    con.close()

    payload = run_backup_job()
    assert payload["status"] == "ok"
    assert "bundle_path" in payload
    daily = list((data / "backups").glob("wash-alpha-*-daily.tar.gz"))
    assert len(daily) == 1


def test_run_backup_job_returns_error_payload_on_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    # No ~/.net_alpha or DB → create_bundle will raise FileNotFoundError.
    (tmp_path / ".net_alpha").mkdir()
    payload = run_backup_job()
    assert payload["status"] == "error"
    assert "error" in payload
