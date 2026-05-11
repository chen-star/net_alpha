"""Pure-function retention policy for backup bundles."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackupFile:
    path: Path
    reason: str
    created_at: datetime
    size_bytes: int


@dataclass(frozen=True)
class RetentionPolicy:
    daily_keep: int = 14
    pre_keep: int = 10
    size_cap_bytes: int = 2 * 1024 ** 3  # 2 GB


def select_for_deletion(
    bundles: list[BackupFile],
    *,
    policy: RetentionPolicy,
    now: datetime,
) -> list[BackupFile]:
    """Return the bundles that should be deleted under `policy`.

    Order of operations:
      1. Manual bundles are never selected.
      2. Daily bundles: keep newest `daily_keep`, delete the rest.
      3. Pre-* bundles: keep newest `pre_keep` (across all pre-reasons), delete the rest.
      4. Size cap: if surviving bundles exceed `size_cap_bytes`, delete oldest
         non-manual bundles until under cap.
      5. If manual bundles alone exceed cap, log a warning and prune nothing more.
    """
    deleted: set[BackupFile] = set()

    daily = sorted(
        [b for b in bundles if b.reason == "daily"],
        key=lambda b: b.created_at,
        reverse=True,
    )
    deleted.update(daily[policy.daily_keep :])

    pre = sorted(
        [b for b in bundles if b.reason.startswith("pre-")],
        key=lambda b: b.created_at,
        reverse=True,
    )
    deleted.update(pre[policy.pre_keep :])

    survivors = [b for b in bundles if b not in deleted]
    total = sum(b.size_bytes for b in survivors)

    if total > policy.size_cap_bytes:
        non_manual_survivors = sorted(
            [b for b in survivors if b.reason != "manual"],
            key=lambda b: b.created_at,
        )
        for b in non_manual_survivors:
            if total <= policy.size_cap_bytes:
                break
            deleted.add(b)
            total -= b.size_bytes

    survivors = [b for b in bundles if b not in deleted]
    total = sum(b.size_bytes for b in survivors)
    if total > policy.size_cap_bytes:
        manual_size = sum(b.size_bytes for b in survivors if b.reason == "manual")
        logger.warning(
            "Manual backups total %.1f MB, exceeding size cap %.1f MB. "
            "Manual bundles are never auto-pruned; run `net-alpha backups rm` to free space.",
            manual_size / 1024 / 1024,
            policy.size_cap_bytes / 1024 / 1024,
        )

    return list(deleted)
