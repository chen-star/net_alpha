"""Job C — daily backup snapshot + retention prune.

Cron: 03:30 UTC (~30 min before the 04:00 UTC washsale_watch). Same timezone
convention as the existing jobs — the AsyncIOScheduler is UTC; users on the
US East Coast see this fire ~23:30 ET.

The job catches its own errors and returns a payload so the runner records a
service_run row with status='ok' or 'error'.
"""

from __future__ import annotations

import net_alpha.backup as backup
from net_alpha.backup.retention import RetentionPolicy


def run_backup_job() -> dict:
    import os

    passphrase = os.environ.get("NETALPHA_BACKUP_PASSPHRASE") or None
    try:
        path = backup.create_bundle(reason="daily", encrypt_passphrase=passphrase)
        pruned = backup.prune(policy=RetentionPolicy())
        return {
            "status": "ok",
            "bundle_path": str(path),
            "pruned_count": len(pruned),
            "encrypted": passphrase is not None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
