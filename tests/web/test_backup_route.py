from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from net_alpha.web.app import create_app


def _seed(home: Path) -> None:
    data = home / ".net_alpha"
    data.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(data / "net_alpha.db")
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO meta VALUES ('schema_version', '20')")
    con.commit()
    con.close()


def test_backup_page_renders(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed(tmp_path)
    app = create_app()
    with TestClient(app) as client:
        r = client.get("/settings/backup")
    assert r.status_code == 200
    assert "Create backup" in r.text
    assert "No backups" in r.text  # empty state


def test_backup_post_create_returns_updated_list(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed(tmp_path)
    app = create_app()
    with TestClient(app) as client:
        r = client.post("/settings/backup/create")
    assert r.status_code == 200
    # HTMX fragment swap returns the updated list.
    assert "manual" in r.text
    backups = list((tmp_path / ".net_alpha" / "backups").glob("*.tar.gz"))
    assert len(backups) == 1
