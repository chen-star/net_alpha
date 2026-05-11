"""`net-alpha backup`, `net-alpha restore`, `net-alpha backups ...` Typer commands."""

from __future__ import annotations

import getpass
import json as _json
from datetime import UTC
from pathlib import Path

import typer
from loguru import logger

import net_alpha.backup as backup
from net_alpha.backup.crypto import BadPassphraseError
from net_alpha.backup.restore import (
    IncompatibleSchemaError,
    dry_run_restore,
    restore_bundle,
)
from net_alpha.db.migrations import CURRENT_SCHEMA_VERSION

backups_app = typer.Typer(no_args_is_help=True, help="List, remove, or prune backup bundles.")


def _prompt_passphrase_confirmed() -> str:
    pw = getpass.getpass("Passphrase: ")
    confirm = getpass.getpass("Confirm passphrase: ")
    if pw != confirm:
        typer.echo("Passphrases did not match.", err=True)
        raise typer.Exit(2)
    if len(pw) < 8:
        typer.echo("Passphrase must be at least 8 characters.", err=True)
        raise typer.Exit(2)
    return pw


def backup_cmd(
    reason: str = typer.Option("manual", "--reason", help="Label for the bundle filename + manifest."),
    encrypt: bool = typer.Option(False, "--encrypt", help="Prompt for a passphrase and AES-256-GCM encrypt."),
):
    """Create a backup bundle in ~/.net_alpha/backups/."""
    pw = _prompt_passphrase_confirmed() if encrypt else None
    try:
        path = backup.create_bundle(reason=reason, encrypt_passphrase=pw)
        typer.echo(f"Created backup: {path}")
        raise typer.Exit(0)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(2)


def restore_cmd(
    bundle: Path = typer.Argument(..., exists=True, help="Path to .tar.gz or .tar.gz.enc bundle."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print manifest + diff; no writes."),
    force: bool = typer.Option(False, "--force", help="Skip the overwrite-confirmation prompt."),
):
    """Restore ~/.net_alpha/ state from a backup bundle."""
    pw = getpass.getpass("Passphrase (leave empty if unencrypted): ") or None
    if bundle.suffix == ".enc" and pw is None:
        typer.echo("Bundle is encrypted; passphrase required.", err=True)
        raise typer.Exit(2)

    try:
        if dry_run:
            result = dry_run_restore(bundle, passphrase=pw, current_schema_version=CURRENT_SCHEMA_VERSION)
            m = result.manifest
            typer.echo(f"Bundle: {bundle.name}")
            typer.echo(f"  reason:         {m.reason}")
            typer.echo(f"  created_at:     {m.created_at.isoformat()}")
            typer.echo(f"  app_version:    {m.app_version}")
            typer.echo(f"  schema_version: {m.schema_version}")
            typer.echo(f"  accounts:       {', '.join(m.account_labels) or '(none)'}")
            typer.echo(f"  row_counts:     {dict(m.row_counts)}")
            typer.echo(f"  encrypted:      {m.encrypted}")
            typer.echo("(dry-run; no changes made)")
            raise typer.Exit(0)

        if not force:
            msg = "Overwrite current ~/.net_alpha/ state? (an existing DB is renamed to .pre-restore-*.bak)"
            if not typer.confirm(msg):
                typer.echo("Cancelled.")
                raise typer.Exit(0)

        # Stop the service if running (best-effort).
        try:
            from net_alpha.service import control

            status = control.status()
            if status.installed and status.running:
                typer.echo("Stopping service before restore...")
                control.stop(reason="restore")
        except Exception as e:
            logger.warning("Could not consult/stop service: {} — proceeding with restore", e)

        result = restore_bundle(bundle, passphrase=pw, current_schema_version=CURRENT_SCHEMA_VERSION)
        typer.echo(f"Restored from {bundle.name}.")
        if result.bak_db_path:
            typer.echo(f"  Previous DB moved to: {result.bak_db_path.name}")
        typer.echo("If you use the always-on service, start it with: net-alpha service start")
        raise typer.Exit(0)
    except (BadPassphraseError, IncompatibleSchemaError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(2)


@backups_app.command("ls")
def backups_ls(json: bool = typer.Option(False, "--json", help="Emit JSON for scripting.")):
    """List backup bundles in ~/.net_alpha/backups/, newest first."""
    bundles = backup.list_bundles()
    if json:
        typer.echo(
            _json.dumps(
                [
                    {
                        "path": str(b.path),
                        "reason": b.reason,
                        "created_at": b.created_at.isoformat(),
                        "size_bytes": b.size_bytes,
                        "encrypted": b.path.suffix == ".enc",
                    }
                    for b in bundles
                ],
                indent=2,
            )
        )
        return
    if not bundles:
        typer.echo("No backups.")
        return
    for b in bundles:
        size_mb = b.size_bytes / 1024 / 1024
        enc = " [encrypted]" if b.path.suffix == ".enc" else ""
        typer.echo(f"{b.created_at.isoformat()}  {b.reason:<16}  {size_mb:>6.1f} MB  {b.path.name}{enc}")


@backups_app.command("rm")
def backups_rm(
    bundle: Path = typer.Argument(..., exists=True),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
):
    """Delete a specific bundle."""
    if not yes:
        if not typer.confirm(f"Delete {bundle.name}?"):
            return
    bundle.unlink()
    typer.echo(f"Deleted {bundle.name}.")


@backups_app.command("prune")
def backups_prune(dry_run: bool = typer.Option(False, "--dry-run")):
    """Apply retention policy: 14 daily + 10 pre-mutation + 2GB cap; manual is sacred."""
    if dry_run:
        from datetime import datetime

        from net_alpha.backup.retention import RetentionPolicy, select_for_deletion

        bundles = backup.list_bundles()
        deleted = select_for_deletion(bundles, policy=RetentionPolicy(), now=datetime.now(UTC))
        for b in deleted:
            typer.echo(f"would delete: {b.path.name}")
        typer.echo(f"({len(deleted)} bundles)")
        return
    deleted_paths = backup.prune()
    for p in deleted_paths:
        typer.echo(f"deleted: {p.name}")
    typer.echo(f"({len(deleted_paths)} bundles pruned)")
