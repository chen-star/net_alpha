"""The 'service is stopped' latch.

When this file exists, the launchd wrapper exits 0 immediately. This is
the safety latch that makes Stop survive reboots, logins, and crashes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from net_alpha.service import paths


def set(reason: str = "manual stop") -> None:
    paths.ensure_dirs()
    ts = datetime.now(timezone.utc).isoformat()  # noqa: UP017
    paths.disabled_flag().write_text(f"{ts}\n{reason}\n")


def is_set() -> bool:
    return paths.disabled_flag().exists()


def clear() -> None:
    p = paths.disabled_flag()
    if p.exists():
        p.unlink()
