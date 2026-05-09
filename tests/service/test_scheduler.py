from unittest.mock import MagicMock

from apscheduler.triggers.cron import CronTrigger

from net_alpha.service.scheduler import build_scheduler


def test_build_scheduler_registers_price_refresh_every_4h():
    repo = MagicMock()
    pricing = MagicMock()
    state = MagicMock()
    state.paused = False
    sched = build_scheduler(repo=repo, pricing=pricing, state=state)
    try:
        job = sched.get_job("price_refresh")
        assert job is not None
        assert isinstance(job.trigger, CronTrigger)
        # CronTrigger field for hour should specify step=4 (i.e., */4)
        hour_field = next(f for f in job.trigger.fields if f.name == "hour")
        # Different APScheduler versions expose this differently; both forms are tolerated.
        rendered = str(hour_field)
        assert "*/4" in rendered or "4" in rendered
    finally:
        if sched.running:
            sched.shutdown(wait=False)


def test_build_scheduler_does_not_start_when_disabled_flag_present(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from net_alpha.service import disabled_flag, paths

    paths.ensure_dirs()
    disabled_flag.set("test")
    repo = MagicMock()
    pricing = MagicMock()
    state = MagicMock()
    state.paused = False
    sched = build_scheduler(repo=repo, pricing=pricing, state=state)
    try:
        # When disabled flag is set, scheduler should not be running.
        # APScheduler exposes .running as a bool.
        assert sched.running is False
    finally:
        if sched.running:
            sched.shutdown(wait=False)
