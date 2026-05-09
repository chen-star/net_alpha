"""In-memory mirror of service runtime state.

Survives only as long as the process. Persistent records live in the
service_run table; this class is the fast-path for the status pill and
health page.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class JobRun:
    job_name: str
    started_at: datetime
    duration_ms: int
    status: str  # 'ok' | 'error' | 'partial'
    error_msg: str | None = None


@dataclass
class ServiceState:
    paused: bool = False
    started_at: datetime | None = None
    max_runs_kept: int = 100
    recent_runs: deque[JobRun] = field(default_factory=lambda: deque(maxlen=100))

    def __post_init__(self):
        # Re-bind recent_runs with the configured cap
        self.recent_runs = deque(maxlen=self.max_runs_kept)

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def record_run(self, run: JobRun) -> None:
        self.recent_runs.append(run)

    def consecutive_failures(self, job_name: str) -> int:
        count = 0
        for r in reversed(self.recent_runs):
            if r.job_name != job_name:
                continue
            if r.status == "ok":
                return count
            count += 1
        return count

    def last_run(self, job_name: str) -> JobRun | None:
        for r in reversed(self.recent_runs):
            if r.job_name == job_name:
                return r
        return None
