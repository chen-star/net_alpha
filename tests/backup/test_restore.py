from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import net_alpha.backup as backup
from net_alpha.backup.restore import (
    IncompatibleSchemaError,
    RestoreResult,
    dry_run_restore,
    restore_bundle,
)


def _seed_db(path: Path, schema_version: int = 20) -> None:
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO meta VALUES ('schema_version', ?)", (str(schema_version),))
    con.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY, ticker TEXT)")
    con.execute("INSERT INTO trades (ticker) VALUES ('AAPL'), ('MSFT')")
    con.commit()
    con.close()


def test_dry_run_returns_manifest_without_mutating(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    data = tmp_path / ".net_alpha"
    data.mkdir()
    _seed_db(data / "net_alpha.db")
    bundle_path = backup.create_bundle(reason="manual")
    # Mutate live DB after backup so we can diff.
    con = sqlite3.connect(data / "net_alpha.db")
    con.execute("INSERT INTO trades (ticker) VALUES ('NVDA')")
    con.commit()
    con.close()

    result = dry_run_restore(bundle_path, passphrase=None, current_schema_version=20)
    assert isinstance(result, RestoreResult)
    assert result.manifest.reason == "manual"
    # Live DB still has 3 rows; bundle has 2.
    con = sqlite3.connect(data / "net_alpha.db")
    assert con.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 3
    con.close()


def test_restore_renames_existing_db_to_bak(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    data = tmp_path / ".net_alpha"
    data.mkdir()
    _seed_db(data / "net_alpha.db")
    bundle_path = backup.create_bundle(reason="manual")
    # Mutate live DB after backup.
    con = sqlite3.connect(data / "net_alpha.db")
    con.execute("INSERT INTO trades (ticker) VALUES ('NVDA')")
    con.commit()
    con.close()
    # Now restore.
    restore_bundle(bundle_path, passphrase=None, current_schema_version=20)
    # A .bak with the pre-restore content exists.
    bak_files = list(data.glob("net_alpha.db.pre-restore-*.bak"))
    assert len(bak_files) == 1
    con = sqlite3.connect(bak_files[0])
    assert con.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 3
    con.close()
    # The active DB is the restored one (2 rows).
    con = sqlite3.connect(data / "net_alpha.db")
    assert con.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 2
    con.close()


def test_restore_refuses_newer_schema(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    data = tmp_path / ".net_alpha"
    data.mkdir()
    _seed_db(data / "net_alpha.db", schema_version=99)
    bundle_path = backup.create_bundle(reason="manual")
    with pytest.raises(IncompatibleSchemaError):
        restore_bundle(bundle_path, passphrase=None, current_schema_version=20)


def test_restore_verifies_db_sha256(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    data = tmp_path / ".net_alpha"
    data.mkdir()
    _seed_db(data / "net_alpha.db")
    bundle_path = backup.create_bundle(reason="manual")
    # Corrupt the bundle: re-archive with a different DB.
    import io
    import tarfile

    raw = bundle_path.read_bytes()
    # Strip the gzip layer and rewrite an inner file.
    buf = io.BytesIO(raw)
    with tarfile.open(fileobj=buf, mode="r:gz") as tf:
        members = tf.getmembers()
        out_buf = io.BytesIO()
        with tarfile.open(fileobj=out_buf, mode="w:gz") as new_tf:
            for m in members:
                if m.name == "db/net_alpha.db":
                    bad_bytes = b"NOT A REAL SQLITE DB"
                    bad_info = tarfile.TarInfo(name=m.name)
                    bad_info.size = len(bad_bytes)
                    new_tf.addfile(bad_info, io.BytesIO(bad_bytes))
                else:
                    extracted = tf.extractfile(m)
                    new_tf.addfile(m, extracted)
    bundle_path.write_bytes(out_buf.getvalue())

    with pytest.raises(ValueError, match="sha256"):
        restore_bundle(bundle_path, passphrase=None, current_schema_version=20)
