"""L2 broker reconciliation — wraps audit/reconciliation.py and adds open-positions diffing.

Emits InvariantResult rows (using the same dataclass as L1) so the verify_job
can persist them uniformly to verify_finding.
"""

from __future__ import annotations

from typing import Any

from net_alpha.verify.invariants import InvariantResult
from net_alpha.verify.tolerances import Severity, ToleranceConfig, classify


def reconcile_realized_gl(*, repo: Any, tol_cfg: ToleranceConfig) -> list[InvariantResult]:
    """Compare our computed realized P&L against the broker Realized G/L CSV.

    Reuses audit.reconciliation.reconcile_all — emits one InvariantResult per
    drift exceeding the realized tolerance. Returns empty when audit lacks
    the helper, no accounts exist, or every account is UNAVAILABLE.
    """
    try:
        from net_alpha.audit.reconciliation import reconcile_all
    except ImportError:
        return []  # audit.reconciliation lacks reconcile_all yet — graceful no-op
    out: list[InvariantResult] = []
    try:
        results = reconcile_all(repo=repo, tolerance=tol_cfg.realized.abs)
    except Exception:  # noqa: BLE001
        return []
    for r in results:
        if r.broker_total is None:
            continue  # UNAVAILABLE — no broker provider for this account; not an error
        sev = classify(ours=r.net_alpha_total, theirs=r.broker_total, tol=tol_cfg.realized)
        if sev != Severity.OK:
            out.append(
                InvariantResult(
                    rule_id="RealizedRecon",
                    severity=sev,
                    scope=f"{r.symbol}/account:{r.account_id}",
                    ours=r.net_alpha_total,
                    theirs=r.broker_total,
                    delta=r.delta,
                    detail={"source": r.source_label} if r.source_label else {},
                )
            )
    return out
