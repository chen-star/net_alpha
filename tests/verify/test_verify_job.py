"""Tests for service/jobs/verify.py — orchestrator that ties recon + persistence."""

from __future__ import annotations

from unittest.mock import MagicMock

from net_alpha.service.jobs.verify import run_verify_once


def test_run_verify_once_writes_a_result_row(tmp_path, monkeypatch):
    monkeypatch.setenv("NET_ALPHA_DIR", str(tmp_path))
    repo = MagicMock()
    repo.latest_broker_positions.return_value = ([], None)  # stale — no positions CSV ever
    repo.aggregate_open_positions.return_value = []
    repo.save_verify_run.return_value = 42
    out = run_verify_once(repo=repo, trigger="manual")
    assert out["verify_result_id"] == 42
    repo.save_verify_run.assert_called_once()
    call_kwargs = repo.save_verify_run.call_args.kwargs
    assert call_kwargs["status"] == "stale"
    assert call_kwargs["trigger"] == "manual"


def test_run_verify_once_records_ok_status_when_no_findings(tmp_path, monkeypatch):
    monkeypatch.setenv("NET_ALPHA_DIR", str(tmp_path))
    repo = MagicMock()
    repo.latest_broker_positions.return_value = (
        [
            type(
                "BP",
                (),
                {
                    "import_id": 1,
                    "account_label": "x",
                    "symbol": "AAPL",
                    "qty": 100.0,
                    "cost_basis": 1000.0,
                    "market_value": 1100.0,
                    "unrealized_pl": 100.0,
                    "as_of_date": "2026-05-11",
                },
            )()
        ],
        "2026-05-11",
    )
    repo.aggregate_open_positions.return_value = [
        {
            "symbol": "AAPL",
            "account_label": "x",
            "qty": 100.0,
            "adjusted_basis_total": 1000.0,
            "market_value_total": 1100.0,
        },
    ]
    repo.save_verify_run.return_value = 99
    out = run_verify_once(repo=repo, trigger="scheduled")
    assert out["verify_result_id"] == 99
    call_kwargs = repo.save_verify_run.call_args.kwargs
    assert call_kwargs["status"] == "ok"
    assert call_kwargs["checks_failed"] == 0
