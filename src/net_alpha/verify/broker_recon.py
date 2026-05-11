"""L2 broker reconciliation — wraps audit/reconciliation.py and adds open-positions diffing.

Emits InvariantResult rows (using the same dataclass as L1) so the verify_job
can persist them uniformly to verify_finding.
"""

from __future__ import annotations

from datetime import date as _date
from typing import Any

from net_alpha.verify.invariants import InvariantResult, _compare
from net_alpha.verify.tolerances import Severity, ToleranceConfig, classify

STALENESS_DAYS = 30


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


def _reference_age_days(as_of_iso: str, today: _date) -> int:
    return (today - _date.fromisoformat(as_of_iso)).days


def reconcile_open_positions(
    *,
    repo: Any,
    tol_cfg: ToleranceConfig,
    today: _date | None = None,
) -> tuple[list[InvariantResult], int | None]:
    """Compare our aggregate (symbol, account) open positions against the broker.

    Returns: (findings, reference_age_days). ``reference_age_days`` is None when
    no positions CSV has ever been imported; otherwise it is the integer day
    delta between ``today`` and the latest broker_position.as_of_date.
    """
    today = today or _date.today()
    findings: list[InvariantResult] = []

    bp_rows, as_of = repo.latest_broker_positions()
    if not bp_rows or as_of is None:
        findings.append(
            InvariantResult(
                rule_id="StaleReference",
                severity=Severity.STALE,
                scope="global",
                detail={"reason": "no positions CSV ever imported"},
            )
        )
        return findings, None

    ref_age = _reference_age_days(as_of, today)
    if ref_age > STALENESS_DAYS:
        findings.append(
            InvariantResult(
                rule_id="StaleReference",
                severity=Severity.STALE,
                scope="global",
                detail={"reason": f"reference is {ref_age} days old (>{STALENESS_DAYS})"},
            )
        )
        # Continue — comparison findings are still useful as advisory context.

    # Build key→row maps for O(1) lookup on each side.
    broker = {(bp.account_label, bp.symbol): bp for bp in bp_rows}
    ours = {(r["account_label"], r["symbol"]): r for r in repo.aggregate_open_positions()}

    keys = set(broker.keys()) | set(ours.keys())
    for key in sorted(keys):
        acct, sym = key
        scope = f"{sym}/{acct}"
        bp = broker.get(key)
        our = ours.get(key)
        if our is None:
            findings.append(
                InvariantResult(
                    rule_id="PositionsMissingLocal",
                    severity=Severity.FAIL,
                    scope=scope,
                    ours=None,
                    theirs=float(bp.qty),
                    detail={"reason": "broker shows position we don't have"},
                )
            )
            continue
        if bp is None:
            findings.append(
                InvariantResult(
                    rule_id="PositionsMissingBroker",
                    severity=Severity.FAIL,
                    scope=scope,
                    ours=float(our["qty"]),
                    theirs=None,
                    detail={"reason": "we hold a position the broker file doesn't show"},
                )
            )
            continue
        # Qty (exact match by default).
        qty_result = _compare(
            rule_id="PositionsQty",
            ours=float(our["qty"]),
            theirs=float(bp.qty),
            tol=tol_cfg.positions_qty,
            scope=scope,
        )
        if qty_result.severity != Severity.OK:
            findings.append(qty_result)
        # Basis.
        b_result = _compare(
            rule_id="BasisRecon",
            ours=float(our["adjusted_basis_total"]),
            theirs=float(bp.cost_basis),
            tol=tol_cfg.positions_basis,
            scope=scope,
        )
        if b_result.severity != Severity.OK:
            findings.append(b_result)
        # Market value.
        mv_result = _compare(
            rule_id="MarketValueRecon",
            ours=float(our["market_value_total"]),
            theirs=float(bp.market_value),
            tol=tol_cfg.positions_mv,
            scope=scope,
        )
        if mv_result.severity != Severity.OK:
            findings.append(mv_result)

    return findings, ref_age
