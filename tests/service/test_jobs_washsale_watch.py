"""Tests for the washsale_watch background job."""

from datetime import date
from unittest.mock import MagicMock as MM

from net_alpha.service.jobs.washsale_watch import run_washsale_watch


def _row(*, id: int, symbol: str, target_amount: str = "10", target_unit: str = "shares") -> MM:
    return MM(id=id, symbol=symbol, target_amount=target_amount, target_unit=target_unit)


def _account(*, broker: str = "schwab", label: str = "personal") -> MM:
    return MM(broker=broker, label=label)


def test_run_washsale_watch_iterates_targets_and_persists_results(monkeypatch):
    """Job hands each (target_row, account) pair to the engine and upserts the
    worst-severity result per target_id. With a single account the worst is
    just the engine's verdict for that pair."""
    repo = MM()
    repo.list_target_rows.return_value = [
        _row(id=1, symbol="SPY"),
        _row(id=2, symbol="TSLA"),
    ]
    repo.list_accounts.return_value = [_account()]

    from net_alpha.engine import washsale_watch as ws_mod

    fake_results = {
        "SPY": ws_mod.WatchResult(status="clean", severity="none"),
        "TSLA": ws_mod.WatchResult(
            status="ira_trap_risk", severity="hard", reason="x", triggering_trade_ids=[42]
        ),
    }
    monkeypatch.setattr(ws_mod, "evaluate_target", lambda **kw: fake_results[kw["target"].symbol])

    payload = run_washsale_watch(repo=repo, today=date(2026, 5, 1))
    assert payload == {"targets": 2, "risk": 1}
    assert repo.upsert_watch_result.call_count == 2

    calls = repo.upsert_watch_result.call_args_list
    risk_call = next(c for c in calls if c.kwargs["target_id"] == 2)
    assert risk_call.kwargs["severity"] == "hard"
    assert risk_call.kwargs["triggering"] == "[42]"


def test_run_washsale_watch_picks_worst_severity_across_accounts(monkeypatch):
    """Two accounts × one target → upsert the worst severity (hard > soft > none)."""
    repo = MM()
    repo.list_target_rows.return_value = [_row(id=7, symbol="SPY")]
    repo.list_accounts.return_value = [
        _account(broker="schwab", label="taxable"),
        _account(broker="fido", label="taxable"),
    ]

    from net_alpha.engine import washsale_watch as ws_mod

    # The fido pass returns hard; the schwab pass returns soft. Job should keep hard.
    seq = iter(
        [
            ws_mod.WatchResult(status="ira_trap_risk", severity="soft", reason="a"),
            ws_mod.WatchResult(
                status="ira_trap_risk", severity="hard", reason="b", triggering_trade_ids=[9]
            ),
        ]
    )
    monkeypatch.setattr(ws_mod, "evaluate_target", lambda **kw: next(seq))

    payload = run_washsale_watch(repo=repo, today=date(2026, 5, 1))
    assert payload == {"targets": 1, "risk": 1}
    call = repo.upsert_watch_result.call_args
    assert call.kwargs["severity"] == "hard"
    assert call.kwargs["reason"] == "b"


def test_run_washsale_watch_default_today_is_today(monkeypatch):
    repo = MM()
    repo.list_target_rows.return_value = []
    repo.list_accounts.return_value = []
    payload = run_washsale_watch(repo=repo)  # no today arg
    assert payload == {"targets": 0, "risk": 0}
