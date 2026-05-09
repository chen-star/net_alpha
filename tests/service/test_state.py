from datetime import datetime, timezone  # noqa: UP017

from net_alpha.service.state import JobRun, ServiceState


def test_state_starts_unpaused():
    s = ServiceState()
    assert s.paused is False


def test_pause_and_resume():
    s = ServiceState()
    s.pause()
    assert s.paused is True
    s.resume()
    assert s.paused is False


def test_record_run_appends_and_caps():
    s = ServiceState(max_runs_kept=3)
    for i in range(5):
        s.record_run(
            JobRun(
                job_name="x",
                started_at=datetime.now(timezone.utc),  # noqa: UP017
                duration_ms=10,
                status="ok",
            )
        )
    assert len(s.recent_runs) == 3


def test_consecutive_failures_counts():
    s = ServiceState()
    for st in ["ok", "error", "error", "error"]:
        s.record_run(
            JobRun(
                job_name="x",
                started_at=datetime.now(timezone.utc),  # noqa: UP017
                duration_ms=1,
                status=st,
            )
        )
    assert s.consecutive_failures("x") == 3


def test_consecutive_failures_resets_on_ok():
    s = ServiceState()
    for st in ["error", "error", "ok"]:
        s.record_run(
            JobRun(
                job_name="x",
                started_at=datetime.now(timezone.utc),  # noqa: UP017
                duration_ms=1,
                status=st,
            )
        )
    assert s.consecutive_failures("x") == 0


def test_last_run_returns_most_recent_for_job():
    s = ServiceState()
    early = JobRun(job_name="x", started_at=datetime.now(timezone.utc), duration_ms=1, status="ok")  # noqa: UP017
    late = JobRun(job_name="x", started_at=datetime.now(timezone.utc), duration_ms=2, status="ok")  # noqa: UP017
    other = JobRun(job_name="y", started_at=datetime.now(timezone.utc), duration_ms=3, status="ok")  # noqa: UP017
    s.record_run(early)
    s.record_run(other)
    s.record_run(late)
    assert s.last_run("x") is late
    assert s.last_run("y") is other
    assert s.last_run("missing") is None
