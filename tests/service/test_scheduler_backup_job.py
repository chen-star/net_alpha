from __future__ import annotations

from unittest.mock import MagicMock

from net_alpha.service.scheduler import build_scheduler


def test_backup_job_registered():
    repo = MagicMock()
    pricing = MagicMock()
    state = MagicMock()
    sched = build_scheduler(repo=repo, pricing=pricing, state=state)
    job_ids = {j.id for j in sched.get_jobs()}
    assert "backup" in job_ids


def test_backup_job_cron_is_0330_utc():
    repo = MagicMock()
    pricing = MagicMock()
    state = MagicMock()
    sched = build_scheduler(repo=repo, pricing=pricing, state=state)
    backup_job = next(j for j in sched.get_jobs() if j.id == "backup")
    # CronTrigger fields are validated by stringifying.
    s = str(backup_job.trigger)
    assert "hour='3'" in s
    assert "minute='30'" in s
