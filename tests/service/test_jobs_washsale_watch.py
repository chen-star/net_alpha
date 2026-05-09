"""Tests for the washsale_watch background job."""

from datetime import date
from unittest.mock import MagicMock as MM

from net_alpha.service.jobs.washsale_watch import run_washsale_watch


def test_run_washsale_watch_iterates_targets_and_persists_results(monkeypatch):
    repo = MM()
    target_a = MM(id=1, symbol="SPY", account="schwab-personal")
    target_b = MM(id=2, symbol="TSLA", account="schwab-personal")
    repo.list_position_targets.return_value = [target_a, target_b]

    from net_alpha.engine import washsale_watch as ws_mod

    fake_results = {
        1: ws_mod.WatchResult(status="clean", severity="none"),
        2: ws_mod.WatchResult(status="ira_trap_risk", severity="hard", reason="x", triggering_trade_ids=[42]),
    }
    monkeypatch.setattr(ws_mod, "evaluate_target", lambda **kw: fake_results[kw["target"].id])

    payload = run_washsale_watch(repo=repo, today=date(2026, 5, 1))
    assert payload == {"targets": 2, "risk": 1}
    assert repo.upsert_watch_result.call_count == 2

    # Confirm the IRA-trap row got severity='hard' and triggering JSON-encoded
    calls = repo.upsert_watch_result.call_args_list
    risk_call = next(c for c in calls if c.kwargs["target_id"] == 2)
    assert risk_call.kwargs["severity"] == "hard"
    assert risk_call.kwargs["triggering"] == "[42]"


def test_run_washsale_watch_default_today_is_today(monkeypatch):
    repo = MM()
    repo.list_position_targets.return_value = []
    payload = run_washsale_watch(repo=repo)  # no today arg
    assert payload == {"targets": 0, "risk": 0}
