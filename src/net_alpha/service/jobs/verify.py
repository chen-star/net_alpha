"""Job — L2 broker reconciliation.

Runs ``verify.broker_recon.reconcile_realized_gl`` + ``reconcile_open_positions``,
rolls findings into a verify_result row + N verify_finding rows.

Schedule: weekly Sunday 04:30 (registered by ``service/scheduler.py`` in
Phase 6). Also triggered inline on every trade-CSV import, every positions-CSV
import, and via ``POST /verify/run``.
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime
from typing import Any

from net_alpha.verify.broker_recon import (
    reconcile_open_positions,
    reconcile_realized_gl,
)
from net_alpha.verify.suppress import is_suppressed, load_suppressions
from net_alpha.verify.tolerances import Severity, load_tolerances


def _status_from_findings(findings: list) -> str:
    """Roll up worst-severity finding into a single status string.

    Order: fail > stale > warn > ok. A run with only stale findings reports
    "stale" so the UI can surface the underlying "import a fresh positions
    CSV" hint instead of a generic ok/warn badge.
    """
    if any(f.severity == Severity.FAIL for f in findings):
        return "fail"
    if any(f.severity == Severity.STALE for f in findings):
        return "stale"
    if any(f.severity == Severity.WARN for f in findings):
        return "warn"
    return "ok"


def run_verify_once(*, repo: Any, trigger: str, today: date | None = None) -> dict:
    """Run one full verify cycle (realized + open positions) and persist.

    Returns a small dict with ``verify_result_id`` (the new row's id) and
    ``status`` so callers can chain UI feedback.
    """
    today = today or date.today()
    tol = load_tolerances()
    started = time.monotonic()

    realized = reconcile_realized_gl(repo=repo, tol_cfg=tol)
    open_pos, ref_age = reconcile_open_positions(repo=repo, tol_cfg=tol, today=today)
    findings = realized + open_pos

    # Apply user-managed suppression rules. Loader returns [] when no config
    # exists, so this is a cheap no-op in the common case.
    rules = load_suppressions()
    if rules:
        findings = [
            f for f in findings if not is_suppressed(rule_id=f.rule_id, scope=f.scope, rules=rules, today=today)
        ]

    duration_ms = int((time.monotonic() - started) * 1000)
    status = _status_from_findings(findings)
    checks_warned = sum(1 for f in findings if f.severity == Severity.WARN)
    checks_failed = sum(1 for f in findings if f.severity == Severity.FAIL)
    # We only record findings (i.e. non-OK results), so "total" here is the
    # count of recorded findings, not the count of comparisons attempted.
    # The L3 property-test suite is the canonical source for "every check passed".
    checks_total = len(findings)
    checks_passed = 0

    verify_result_id = repo.save_verify_run(
        run_at=datetime.now(UTC).isoformat(),
        trigger=trigger,
        status=status,
        duration_ms=duration_ms,
        checks_total=checks_total,
        checks_passed=checks_passed,
        checks_warned=checks_warned,
        checks_failed=checks_failed,
        reference_age_days=ref_age,
        notes=f"{len(findings)} findings",
        findings=findings,
    )
    return {"verify_result_id": verify_result_id, "status": status}


def run_verify_job(*, repo: Any) -> dict:
    """Scheduler-facing wrapper. Matches the ``(repo,)`` signature other jobs use."""
    return run_verify_once(repo=repo, trigger="scheduled")
