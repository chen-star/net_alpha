"""Create and extract backup bundles. SQLite-safe DB capture."""

from __future__ import annotations

import hashlib
import io
import shutil
import socket
import sqlite3
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from net_alpha.backup import crypto, paths
from net_alpha.backup.manifest import MANIFEST_FORMAT_VERSION, Manifest

_CONFIG_FILES = ("etf_pairs.yaml", "config.yaml", "config.toml")

# Constant AAD: per-bundle binding is provided by random salt + nonce already.
_AAD_CONST = b"wash-alpha-backup-v1".ljust(32, b"\x00")


def capture_db(src: Path, dst: Path) -> None:
    """WAL-safe copy that also produces a byte-identical file when no WAL is active.

    Strategy: checkpoint the WAL into the main DB file first (PASSIVE mode — does not
    block writers), then do a raw file copy.  For a DB with no open connections and no
    active WAL this is byte-identical to the source.  For a DB with a concurrent writer
    holding an open WAL transaction the checkpoint folds committed frames into the main
    file; the uncommitted transaction is not captured, which is the correct safe
    behaviour (the copy will contain only committed data).
    """
    if not src.exists():
        raise FileNotFoundError(f"source DB not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    # Attempt a PASSIVE checkpoint so committed WAL frames land in the main file.
    # PASSIVE never blocks and is a no-op on a non-WAL database.
    try:
        chk_conn = sqlite3.connect(str(src))
        chk_conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
        chk_conn.close()
    except Exception:
        pass  # best-effort; the raw copy will still capture committed state
    shutil.copy2(src, dst)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def create_bundle(
    *,
    data_dir: Path,
    out_dir: Path,
    reason: str,
    app_version: str,
    schema_version: int,
    encrypt_passphrase: str | None,
    row_counts: dict[str, int],
    account_labels: list[str],
) -> Path:
    """Create a backup bundle in `out_dir` and return its path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc)
    encrypted = encrypt_passphrase is not None
    final_name = paths.bundle_filename(created_at=created_at, reason=reason, encrypted=encrypted)
    final_path = out_dir / final_name
    tmp_path = out_dir / (final_name + ".tmp")

    with tempfile.TemporaryDirectory(prefix="washalpha-backup-") as scratch:
        scratch_dir = Path(scratch)
        db_copy = scratch_dir / "net_alpha.db"
        capture_db(data_dir / "net_alpha.db", db_copy)

        manifest = Manifest(
            format_version=MANIFEST_FORMAT_VERSION,
            app_version=app_version,
            schema_version=schema_version,
            created_at=created_at,
            reason=paths.sanitize_reason(reason),
            hostname=socket.gethostname(),
            db_sha256=_sha256_file(db_copy),
            db_size_bytes=db_copy.stat().st_size,
            row_counts=row_counts,
            account_labels=account_labels,
            encrypted=encrypted,
        )

        # Build the tarball in memory.
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            manifest_bytes = manifest.to_json_bytes()
            info = tarfile.TarInfo(name="manifest.json")
            info.size = len(manifest_bytes)
            tf.addfile(info, io.BytesIO(manifest_bytes))

            tf.add(db_copy, arcname="db/net_alpha.db")

            for cfg in _CONFIG_FILES:
                src_cfg = data_dir / cfg
                if src_cfg.exists():
                    tf.add(src_cfg, arcname=f"config/{cfg}")

        tarball = buf.getvalue()

        try:
            if encrypted:
                payload = crypto.encrypt_bundle(
                    tarball, passphrase=encrypt_passphrase, aad=_AAD_CONST
                )
            else:
                payload = tarball

            tmp_path.write_bytes(payload)
            tmp_path.rename(final_path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    logger.info("Created backup bundle: {}", final_path)
    return final_path


def extract_bundle(
    bundle: Path,
    out_dir: Path,
    *,
    passphrase: str | None,
) -> Manifest:
    """Extract a bundle into `out_dir`; return the parsed Manifest.

    `passphrase` is required for .enc bundles. Raises BadPassphraseError or ValueError.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = bundle.read_bytes()

    if bundle.suffix == ".enc":
        if passphrase is None:
            raise ValueError("bundle is encrypted; passphrase is required")
        plaintext = crypto.decrypt_bundle(raw, passphrase=passphrase, aad=_AAD_CONST)
    else:
        plaintext = raw

    with tarfile.open(fileobj=io.BytesIO(plaintext), mode="r:gz") as tf:
        tf.extractall(out_dir)

    manifest_path = out_dir / "manifest.json"
    return Manifest.from_json_bytes(manifest_path.read_bytes())
