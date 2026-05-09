"""Wrap a single job invocation in audit + uniform error handling."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from net_alpha.service.state import JobRun, ServiceState


def run_job(
    *,
    job_name: str,
    fn: Callable[[], Any],
    state: ServiceState,
    repo: Any,
) -> Any:
    """Run `fn`. Record outcome in state + repo. Never raises."""
    if state.paused:
        logger.info("Job {} skipped — service is paused", job_name)
        return None

    started = datetime.now(UTC)
    t0 = time.perf_counter()
    try:
        payload = fn()
        elapsed = int((time.perf_counter() - t0) * 1000)
        state.record_run(
            JobRun(
                job_name=job_name,
                started_at=started,
                duration_ms=elapsed,
                status="ok",
            )
        )
        repo.record_service_run(
            job_name=job_name,
            started_at=started.isoformat(),
            finished_at=datetime.now(UTC).isoformat(),
            status="ok",
            duration_ms=elapsed,
            error_msg=None,
            payload=json.dumps(payload) if payload is not None else None,
        )
        return payload
    except Exception as e:
        elapsed = int((time.perf_counter() - t0) * 1000)
        logger.exception("Job {} failed: {}", job_name, e)
        state.record_run(
            JobRun(
                job_name=job_name,
                started_at=started,
                duration_ms=elapsed,
                status="error",
                error_msg=str(e),
            )
        )
        repo.record_service_run(
            job_name=job_name,
            started_at=started.isoformat(),
            finished_at=datetime.now(UTC).isoformat(),
            status="error",
            duration_ms=elapsed,
            error_msg=str(e),
            payload=None,
        )
        return None
