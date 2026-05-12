"""Tests for verify/broker_recon.py — L2 broker reconciliation."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

from net_alpha.verify.broker_recon import reconcile_open_positions, reconcile_realized_gl
from net_alpha.verify.models import BrokerPosition
from net_alpha.verify.tolerances import Severity, load_tolerances


def test_realized_recon_emits_no_findings_when_all_match():
    repo = MagicMock()
    repo.list_accounts.return_value = []  # No accounts → no work → no findings
    findings = reconcile_realized_gl(repo=repo, tol_cfg=load_tolerances())
    assert findings == []


def test_realized_recon_emits_fail_finding_on_drift(monkeypatch):
    from net_alpha.audit import reconciliation as recon_mod
    from net_alpha.audit.reconciliation import ReconciliationResult, ReconciliationStatus

    fake_results = [
        ReconciliationResult(
            symbol="AAPL",
            account_id=1,
            net_alpha_total=1000.0,
            broker_total=950.0,
            delta=50.0,
            status=ReconciliationStatus.DIFF,
            tolerance=0.50,
            source_label="Schwab",
        ),
    ]
    monkeypatch.setattr(recon_mod, "reconcile_all", lambda **kw: fake_results)

    repo = MagicMock()
    findings = reconcile_realized_gl(repo=repo, tol_cfg=load_tolerances())
    assert any(f.rule_id == "RealizedRecon" and f.severity == Severity.FAIL for f in findings)


def _bp(symbol: str, acct: str, qty: float, basis: float, mv: float, as_of: str) -> BrokerPosition:
    return BrokerPosition(
        import_id=1,
        account_label=acct,
        symbol=symbol,
        qty=qty,
        cost_basis=basis,
        market_value=mv,
        unrealized_pl=mv - basis,
        as_of_date=as_of,
    )


def test_open_positions_recon_passes_when_aggregates_match():
    repo = MagicMock()
    today = date(2026, 5, 11).isoformat()
    repo.latest_broker_positions.return_value = (
        [_bp("AAPL", "Schwab-Taxable", 100.0, 15000.0, 17550.0, today)],
        today,
    )
    repo.aggregate_open_positions.return_value = [
        {
            "symbol": "AAPL",
            "account_label": "Schwab-Taxable",
            "qty": 100.0,
            "adjusted_basis_total": 15000.0,
            "market_value_total": 17550.0,
        },
    ]
    findings, ref_age = reconcile_open_positions(repo=repo, tol_cfg=load_tolerances(), today=date(2026, 5, 11))
    assert findings == []
    assert ref_age == 0


def test_open_positions_recon_flags_basis_mismatch():
    repo = MagicMock()
    today = date(2026, 5, 11).isoformat()
    repo.latest_broker_positions.return_value = (
        [_bp("AAPL", "Schwab-Taxable", 100.0, 16000.0, 17550.0, today)],
        today,
    )
    repo.aggregate_open_positions.return_value = [
        {
            "symbol": "AAPL",
            "account_label": "Schwab-Taxable",
            "qty": 100.0,
            "adjusted_basis_total": 15000.0,
            "market_value_total": 17550.0,
        },
    ]
    findings, _ = reconcile_open_positions(repo=repo, tol_cfg=load_tolerances(), today=date(2026, 5, 11))
    rule_ids = {f.rule_id for f in findings}
    assert "BasisRecon" in rule_ids


def test_open_positions_recon_returns_stale_when_no_reference():
    repo = MagicMock()
    repo.latest_broker_positions.return_value = ([], None)
    findings, ref_age = reconcile_open_positions(repo=repo, tol_cfg=load_tolerances(), today=date(2026, 5, 11))
    assert ref_age is None
    assert any(f.severity == Severity.STALE and f.rule_id == "StaleReference" for f in findings)


def test_open_positions_recon_returns_stale_when_old_reference():
    repo = MagicMock()
    old = (date(2026, 5, 11) - timedelta(days=31)).isoformat()
    repo.latest_broker_positions.return_value = ([_bp("AAPL", "X", 1, 1, 1, old)], old)
    repo.aggregate_open_positions.return_value = []
    findings, ref_age = reconcile_open_positions(repo=repo, tol_cfg=load_tolerances(), today=date(2026, 5, 11))
    assert ref_age == 31
    assert any(f.severity == Severity.STALE for f in findings)
