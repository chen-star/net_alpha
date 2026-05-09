from unittest.mock import MagicMock

from net_alpha.service.jobs.runner import run_job
from net_alpha.service.state import ServiceState


def test_run_job_records_success():
    state = ServiceState()
    repo = MagicMock()
    payload = run_job(
        job_name="price_refresh",
        fn=lambda: {"symbols": 5},
        state=state,
        repo=repo,
    )
    assert payload == {"symbols": 5}
    assert state.last_run("price_refresh").status == "ok"
    repo.record_service_run.assert_called_once()
    kw = repo.record_service_run.call_args.kwargs
    assert kw["status"] == "ok"
    assert kw["job_name"] == "price_refresh"
    assert kw["payload"] == '{"symbols": 5}'


def test_run_job_records_failure_and_swallows():
    state = ServiceState()
    repo = MagicMock()

    def boom():
        raise RuntimeError("yfinance down")

    payload = run_job(
        job_name="price_refresh",
        fn=boom,
        state=state,
        repo=repo,
    )
    assert payload is None
    assert state.last_run("price_refresh").status == "error"
    kw = repo.record_service_run.call_args.kwargs
    assert kw["status"] == "error"
    assert "yfinance down" in kw["error_msg"]


def test_run_job_skipped_when_paused():
    state = ServiceState()
    state.pause()
    repo = MagicMock()
    fn = MagicMock()
    payload = run_job(job_name="x", fn=fn, state=state, repo=repo)
    assert payload is None
    fn.assert_not_called()
    repo.record_service_run.assert_not_called()
