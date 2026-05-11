"""Local backup & restore: bundle, encrypt, retain, restore ~/.net_alpha/ state.

Public seams:
  create_bundle(...)   - explicit create + return path
  list_bundles()       - current contents of ~/.net_alpha/backups/, newest first
  prune(policy=...)    - apply retention rules; return list of deleted paths
  snapshot_pre(reason) - convenience wrapper used by pre-mutation hooks; never raises
"""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from net_alpha.backup import bundle as _bundle
from net_alpha.backup import paths
from net_alpha.backup.retention import BackupFile, RetentionPolicy, select_for_deletion

__all__ = ["create_bundle", "list_bundles", "prune", "snapshot_pre"]

_FILENAME_RE = re.compile(r"^wash-alpha-(\d{8})-(\d{6})-(?P<reason>[a-z0-9-]+)\.tar\.gz(?P<enc>\.enc)?$")


def _read_schema_version(db_path: Path) -> int:
    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        return int(row[0]) if row else 0
    finally:
        con.close()


def _read_app_version() -> str:
    try:
        from importlib.metadata import version

        return version("wash-alpha")
    except Exception:
        return "unknown"


def create_bundle(
    *,
    reason: str = "manual",
    encrypt_passphrase: str | None = None,
    row_counts: dict[str, int] | None = None,
    account_labels: list[str] | None = None,
) -> Path:
    """Create a backup bundle in the default location; return its path."""
    data_dir = paths.net_alpha_home()
    out_dir = paths.backups_dir()
    db = data_dir / "net_alpha.db"
    schema_version = _read_schema_version(db) if db.exists() else 0
    return _bundle.create_bundle(
        data_dir=data_dir,
        out_dir=out_dir,
        reason=reason,
        app_version=_read_app_version(),
        schema_version=schema_version,
        encrypt_passphrase=encrypt_passphrase,
        row_counts=row_counts or {},
        account_labels=account_labels or [],
    )


def list_bundles() -> list[BackupFile]:
    """Enumerate bundles in `~/.net_alpha/backups/`, newest first."""
    out: list[BackupFile] = []
    bdir = paths.backups_dir()
    if not bdir.exists():
        return out
    for p in bdir.iterdir():
        m = _FILENAME_RE.match(p.name)
        if not m:
            continue
        ts = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        out.append(
            BackupFile(
                path=p,
                reason=m.group("reason"),
                created_at=ts,
                size_bytes=p.stat().st_size,
            )
        )
    out.sort(key=lambda b: b.created_at, reverse=True)
    return out


def prune(*, policy: RetentionPolicy | None = None) -> list[Path]:
    """Apply retention rules; delete and return the paths that were removed."""
    pol = policy or RetentionPolicy()
    bundles = list_bundles()
    deleted_files = select_for_deletion(bundles, policy=pol, now=datetime.now(UTC))
    out: list[Path] = []
    for b in deleted_files:
        try:
            b.path.unlink()
            out.append(b.path)
            logger.info("Pruned backup: {}", b.path.name)
        except OSError as e:
            logger.warning("Failed to prune {}: {}", b.path, e)
    return out


def snapshot_pre(*, reason: str) -> Path | None:
    """Best-effort pre-mutation snapshot. NEVER raises — failures only warn."""
    try:
        return create_bundle(reason=reason)
    except Exception as e:
        logger.warning("Pre-mutation snapshot ({}) failed: {} — continuing without backup", reason, e)
        return None
