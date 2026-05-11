from __future__ import annotations

import sqlite3
import tarfile
from pathlib import Path

import pytest

from net_alpha.backup.bundle import (
    capture_db,
    create_bundle,
    extract_bundle,
)
from net_alpha.backup.manifest import Manifest


def _seed_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    con.execute("INSERT INTO t (v) VALUES ('hello'), ('world')")
    con.commit()
    con.close()


def test_capture_db_produces_logically_equivalent_copy(tmp_path):
    """The captured DB has the same tables and rows as the source."""
    src = tmp_path / "src.db"
    dst = tmp_path / "dst.db"
    _seed_db(src)
    capture_db(src, dst)
    src_con = sqlite3.connect(src)
    dst_con = sqlite3.connect(dst)
    try:
        src_rows = sorted(src_con.execute("SELECT id, v FROM t").fetchall())
        dst_rows = sorted(dst_con.execute("SELECT id, v FROM t").fetchall())
        assert dst_rows == src_rows
    finally:
        src_con.close()
        dst_con.close()


def test_capture_db_is_wal_safe(tmp_path):
    """A live writer should not corrupt the captured copy."""
    src = tmp_path / "src.db"
    dst = tmp_path / "dst.db"
    _seed_db(src)
    # Open a writer connection that holds the DB; capture should still work.
    writer = sqlite3.connect(src)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("INSERT INTO t (v) VALUES ('mid-write')")
    capture_db(src, dst)
    writer.commit()
    writer.close()
    # The captured DB is openable and contains the seeded rows at minimum.
    con = sqlite3.connect(dst)
    count = con.execute("SELECT COUNT(*) FROM t").fetchone()[0]
    con.close()
    assert count >= 2


def test_create_bundle_writes_tarball_with_db_and_manifest(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    data_dir = home / ".net_alpha"
    data_dir.mkdir()
    db = data_dir / "net_alpha.db"
    _seed_db(db)
    (data_dir / "etf_pairs.yaml").write_text("custom: pairs\n")

    out = create_bundle(
        data_dir=data_dir,
        out_dir=data_dir / "backups",
        reason="manual",
        app_version="0.57.0",
        schema_version=20,
        encrypt_passphrase=None,
        row_counts={"trades": 0},
        account_labels=[],
    )
    assert out.exists()
    assert out.suffix == ".gz"  # unencrypted ends in .tar.gz
    with tarfile.open(out, "r:gz") as tf:
        names = tf.getnames()
    assert "manifest.json" in names
    assert "db/net_alpha.db" in names
    assert "config/etf_pairs.yaml" in names


def test_create_bundle_encrypted(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    data_dir = home / ".net_alpha"
    data_dir.mkdir()
    _seed_db(data_dir / "net_alpha.db")

    out = create_bundle(
        data_dir=data_dir,
        out_dir=data_dir / "backups",
        reason="manual",
        app_version="0.57.0",
        schema_version=20,
        encrypt_passphrase="hunter2",
        row_counts={},
        account_labels=[],
    )
    assert out.suffix == ".enc"
    # First 16 bytes are the WASHALPHA-BAK magic.
    assert out.read_bytes()[:16] == b"WASHALPHA-BAK\x00\x00\x00"


def test_extract_bundle_unencrypted_roundtrip(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    data_dir = home / ".net_alpha"
    data_dir.mkdir()
    _seed_db(data_dir / "net_alpha.db")
    bundle = create_bundle(
        data_dir=data_dir,
        out_dir=data_dir / "backups",
        reason="manual",
        app_version="0.57.0",
        schema_version=20,
        encrypt_passphrase=None,
        row_counts={"trades": 2},
        account_labels=["a/b"],
    )
    extract_dir = tmp_path / "extracted"
    manifest = extract_bundle(bundle, extract_dir, passphrase=None)
    assert isinstance(manifest, Manifest)
    assert manifest.reason == "manual"
    assert (extract_dir / "db" / "net_alpha.db").exists()


def test_extract_bundle_encrypted_roundtrip(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    data_dir = home / ".net_alpha"
    data_dir.mkdir()
    _seed_db(data_dir / "net_alpha.db")
    bundle = create_bundle(
        data_dir=data_dir,
        out_dir=data_dir / "backups",
        reason="manual",
        app_version="0.57.0",
        schema_version=20,
        encrypt_passphrase="pw",
        row_counts={},
        account_labels=[],
    )
    extract_dir = tmp_path / "extracted"
    manifest = extract_bundle(bundle, extract_dir, passphrase="pw")
    assert manifest.encrypted is True
    assert (extract_dir / "db" / "net_alpha.db").exists()


def test_create_bundle_atomic_no_partial_file(tmp_path, monkeypatch):
    """If something blows up mid-write, no .tar.gz appears alongside a stale .tmp."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    data_dir = home / ".net_alpha"
    data_dir.mkdir()
    # No DB file -> capture_db will raise.
    with pytest.raises(Exception):
        create_bundle(
            data_dir=data_dir,
            out_dir=data_dir / "backups",
            reason="manual",
            app_version="0.57.0",
            schema_version=20,
            encrypt_passphrase=None,
            row_counts={},
            account_labels=[],
        )
    backups = list((data_dir / "backups").glob("wash-alpha-*"))
    # No final .tar.gz should exist (the tmp file is best-effort cleaned).
    assert not any(b.suffix in (".gz", ".enc") for b in backups)
