from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

import net_alpha.backup as backup
from net_alpha.backup.retention import BackupFile


def test_public_api_exports():
    assert callable(backup.create_bundle)
    assert callable(backup.list_bundles)
    assert callable(backup.prune)
    assert callable(backup.snapshot_pre)


def test_list_bundles_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert backup.list_bundles() == []


def test_list_bundles_parses_filenames(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    bdir = tmp_path / ".net_alpha" / "backups"
    bdir.mkdir(parents=True)
    (bdir / "wash-alpha-20260510-153045-manual.tar.gz").write_bytes(b"x" * 100)
    (bdir / "wash-alpha-20260509-040000-daily.tar.gz.enc").write_bytes(b"x" * 200)
    (bdir / "unrelated.txt").write_bytes(b"x")  # ignored

    bundles = backup.list_bundles()
    assert len(bundles) == 2
    # Newest first.
    assert bundles[0].reason == "manual"
    assert bundles[1].reason == "daily"


def test_snapshot_pre_creates_a_pre_bundle(tmp_path, monkeypatch):
    import sqlite3

    monkeypatch.setenv("HOME", str(tmp_path))
    data = tmp_path / ".net_alpha"
    data.mkdir()
    con = sqlite3.connect(str(data / "net_alpha.db"))
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO meta VALUES ('schema_version', '20')")
    con.commit()
    con.close()

    path = backup.snapshot_pre(reason="pre-import")
    assert path is not None
    assert path.name.startswith("wash-alpha-")
    assert "pre-import" in path.name


def test_snapshot_pre_does_not_raise_on_missing_db(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".net_alpha").mkdir()
    # No DB. snapshot_pre returns None and logs a warning; does NOT raise.
    result = backup.snapshot_pre(reason="pre-import")
    assert result is None
