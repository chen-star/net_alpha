"""Apply a backup bundle to ~/.net_alpha/ with strict safety checks."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from net_alpha.backup import bundle as _bundle
from net_alpha.backup import paths
from net_alpha.backup.bundle import _sha256_file
from net_alpha.backup.manifest import Manifest

_CONFIG_FILES = ("etf_pairs.yaml", "config.yaml", "config.toml")


class IncompatibleSchemaError(Exception):
    """Bundle schema_version is newer than the running app understands."""


@dataclass(frozen=True)
class RestoreResult:
    manifest: Manifest
    bak_db_path: Path | None


def _validate(extracted_dir: Path, manifest: Manifest, current_schema_version: int) -> None:
    if manifest.schema_version > current_schema_version:
        raise IncompatibleSchemaError(
            f"Bundle schema v{manifest.schema_version} is newer than running app v{current_schema_version}. "
            f"Upgrade wash-alpha first."
        )
    db_path = extracted_dir / "db" / "net_alpha.db"
    if not db_path.exists():
        raise ValueError("bundle is missing db/net_alpha.db")
    actual = _sha256_file(db_path)
    if actual != manifest.db_sha256:
        raise ValueError(
            f"db sha256 mismatch (manifest={manifest.db_sha256[:12]}..., actual={actual[:12]}...) — "
            "bundle is truncated or corrupted"
        )


def dry_run_restore(
    bundle_path: Path,
    *,
    passphrase: str | None,
    current_schema_version: int,
) -> RestoreResult:
    """Extract + validate; perform NO writes to ~/.net_alpha/."""
    with tempfile.TemporaryDirectory(prefix="washalpha-restore-dry-") as scratch_str:
        scratch = Path(scratch_str)
        manifest = _bundle.extract_bundle(bundle_path, scratch, passphrase=passphrase)
        _validate(scratch, manifest, current_schema_version)
        return RestoreResult(manifest=manifest, bak_db_path=None)


def restore_bundle(
    bundle_path: Path,
    *,
    passphrase: str | None,
    current_schema_version: int,
) -> RestoreResult:
    """Atomically replace ~/.net_alpha/ state with the bundle's contents.

    Renames existing DB + config files aside with a .pre-restore-<ts>.bak suffix.
    Caller is responsible for stopping the service before calling.
    """
    data_dir = paths.net_alpha_home()
    data_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="washalpha-restore-") as scratch_str:
        scratch = Path(scratch_str)
        manifest = _bundle.extract_bundle(bundle_path, scratch, passphrase=passphrase)
        _validate(scratch, manifest, current_schema_version)

        ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        db_target = data_dir / "net_alpha.db"
        db_staged = data_dir / f"net_alpha.db.restore-staged-{ts}"
        bak_db = None

        # Step A: copy the new DB into a sibling path. If this fails, the old DB
        # is untouched and the user is no worse off.
        shutil.copy2(scratch / "db" / "net_alpha.db", db_staged)

        # Step B: move old aside, then move new into place. Both are atomic renames
        # on the same filesystem.
        try:
            if db_target.exists():
                bak_db = data_dir / f"net_alpha.db.pre-restore-{ts}.bak"
                db_target.rename(bak_db)
                logger.info("Moved existing DB aside: {}", bak_db.name)
            db_staged.rename(db_target)
        except Exception:
            # Rollback: if we moved the old DB but failed before the new one
            # was in place, put the old one back.
            if bak_db and bak_db.exists() and not db_target.exists():
                bak_db.rename(db_target)
            db_staged.unlink(missing_ok=True)
            raise

        # WAL siblings of the OLD db are stale once we've replaced the file.
        for sibling in (data_dir / "net_alpha.db-wal", data_dir / "net_alpha.db-shm"):
            sibling.unlink(missing_ok=True)

        # Config files: still rename-aside + copy-in, but only after the DB is settled.
        for cfg in _CONFIG_FILES:
            src = data_dir / cfg
            if src.exists():
                src.rename(data_dir / f"{cfg}.pre-restore-{ts}.bak")

        extracted_config = scratch / "config"
        if extracted_config.exists():
            for cfg in _CONFIG_FILES:
                src = extracted_config / cfg
                if src.exists():
                    shutil.copy2(src, data_dir / cfg)

    logger.info(
        "Restored bundle {} (schema v{}, {} accounts)",
        bundle_path.name,
        manifest.schema_version,
        len(manifest.account_labels),
    )
    return RestoreResult(manifest=manifest, bak_db_path=bak_db)
