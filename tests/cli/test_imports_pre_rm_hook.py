from __future__ import annotations

import sqlite3

from net_alpha.cli import imports as imports_cmd


def test_pre_imports_rm_hook_creates_bundle(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    data = tmp_path / ".net_alpha"
    data.mkdir()
    # Build a DB so the engine can open it.
    con = sqlite3.connect(data / "net_alpha.db")
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO meta VALUES ('schema_version', '20')")
    con.commit()
    con.close()

    # remove_cmd(99, yes=True) on a non-existent import returns code 5 — hook should still fire.
    rc = imports_cmd.remove_cmd(99, yes=True)
    assert rc == 5
    bundles = list((data / "backups").glob("wash-alpha-*-pre-imports-rm.tar.gz"))
    assert len(bundles) == 1
