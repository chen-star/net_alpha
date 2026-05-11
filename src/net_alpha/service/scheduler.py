"""APScheduler bootstrap — registers the v2 background jobs.

NOTE: build_scheduler intentionally does NOT start the scheduler. Starting
requires a running asyncio event loop (AsyncIOScheduler), which is not
available in sync test environments or at module-import time. The FastAPI
lifespan in Task 2.8 is responsible for calling sched.start() / sched.shutdown()
at the right moment. This also means the disabled-flag check is advisory here:
when the flag is set the scheduler is returned un-started, and the lifespan
should respect that by not calling start() either.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from net_alpha.service import disabled_flag
from net_alpha.service.jobs.backup import run_backup_job
from net_alpha.service.jobs.price_refresh import run_price_refresh
from net_alpha.service.jobs.runner import run_job
from net_alpha.service.jobs.verify import run_verify_job
from net_alpha.service.jobs.washsale_watch import run_washsale_watch


def build_scheduler(*, repo, pricing, state) -> AsyncIOScheduler:
    """Build (but do NOT start) the AsyncIOScheduler with the v2 jobs.

    Callers (e.g. FastAPI lifespan) are responsible for calling
    ``sched.start()`` and ``sched.shutdown()``. The disabled_flag check is
    exposed via ``disabled_flag.is_set()`` so the caller can skip start when
    the service is latched off.
    """
    sched = AsyncIOScheduler(timezone="UTC")

    sched.add_job(
        func=run_job,
        kwargs={
            "job_name": "price_refresh",
            "fn": lambda: run_price_refresh(repo=repo, pricing=pricing),
            "state": state,
            "repo": repo,
        },
        id="price_refresh",
        trigger=CronTrigger(hour="*/4"),
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
    )

    sched.add_job(
        func=run_job,
        kwargs={
            "job_name": "washsale_watch",
            "fn": lambda: run_washsale_watch(repo=repo),
            "state": state,
            "repo": repo,
        },
        id="washsale_watch",
        trigger=CronTrigger(hour=4, minute=0),
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )

    sched.add_job(
        func=run_job,
        kwargs={
            "job_name": "backup",
            "fn": run_backup_job,
            "state": state,
            "repo": repo,
        },
        id="backup",
        trigger=CronTrigger(hour=3, minute=30),
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )

    # Weekly L2 broker reconciliation. Sunday 04:30 UTC sits an hour after the
    # daily 04:00 washsale watch and a full hour after the 03:30 backup, so the
    # three jobs never overlap. misfire_grace_time covers laptop-slept-through-
    # window scenarios; coalesce collapses any pile-up to a single run.
    sched.add_job(
        func=run_job,
        kwargs={
            "job_name": "verify",
            "fn": lambda: run_verify_job(repo=repo),
            "state": state,
            "repo": repo,
        },
        id="verify",
        trigger=CronTrigger(day_of_week="sun", hour=4, minute=30),
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )

    return sched


def is_disabled() -> bool:
    """Return True when the disabled flag latch is set (service should not run)."""
    return disabled_flag.is_set()
