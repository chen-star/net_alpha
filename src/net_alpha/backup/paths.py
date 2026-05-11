"""Filesystem paths and filename conventions for backup bundles."""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

KNOWN_REASONS = frozenset({"manual", "daily", "pre-import", "pre-imports-rm", "pre-migrate"})


def home() -> Path:
    return Path(os.environ.get("HOME", str(Path.home())))


def net_alpha_home() -> Path:
    return home() / ".net_alpha"


def backups_dir() -> Path:
    return net_alpha_home() / "backups"


def ensure_backups_dir() -> Path:
    d = backups_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def sanitize_reason(reason: str) -> str:
    """Lowercase + collapse to [a-z0-9-]; empty -> 'manual'."""
    cleaned = re.sub(r"[^a-z0-9-]+", "-", reason.lower()).strip("-")
    return cleaned or "manual"


def bundle_filename(*, created_at: datetime, reason: str, encrypted: bool) -> str:
    ts = created_at.strftime("%Y%m%d-%H%M%S")
    safe_reason = sanitize_reason(reason)
    suffix = ".tar.gz.enc" if encrypted else ".tar.gz"
    return f"wash-alpha-{ts}-{safe_reason}{suffix}"
