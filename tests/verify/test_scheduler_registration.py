"""Phase 6 / Task 17: verify job registration in the APScheduler factory.

The verify job runs weekly on Sunday at 04:30 UTC. This test pins the trigger
fields so a future drift (someone changes the day or time) is loud.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from net_alpha.service.scheduler import build_scheduler


def test_verify_job_is_registered_weekly_sunday_0430():
    sched = build_scheduler(repo=MagicMock(), pricing=MagicMock(), state=MagicMock())
    try:
        job = sched.get_job("verify")
        assert job is not None, "verify job not registered"
        # APScheduler exposes trigger fields via .fields; each field renders
        # the cron expression for that slot.
        fields = {f.name: str(f) for f in job.trigger.fields}
        assert "sun" in fields.get("day_of_week", "").lower()
        assert fields.get("hour", "") == "4"
        assert fields.get("minute", "") == "30"
    finally:
        if sched.running:
            sched.shutdown(wait=False)
