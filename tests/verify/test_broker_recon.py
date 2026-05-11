"""Tests for verify/broker_recon.py — L2 broker reconciliation."""

from __future__ import annotations

from unittest.mock import MagicMock

from net_alpha.verify.broker_recon import reconcile_realized_gl
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
