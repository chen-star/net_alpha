"""Pure invariant-check functions for the L1 inline badge and the L3 property tests.

Each check takes already-computed numbers and returns an InvariantResult. The
caller is responsible for assembling the numbers from a Repository or snapshot.

Why pure: the same check function runs in both the inline render path and
the Hypothesis property tests, guaranteeing the badge and CI agree on what
"correct" means.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date as _date
from typing import Any

from net_alpha.verify.tolerances import Severity, Tolerance, classify


@dataclass(frozen=True)
class InvariantResult:
    rule_id: str
    severity: Severity
    scope: str = "global"
    ours: float | None = None
    theirs: float | None = None
    delta: float | None = None
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "scope": self.scope,
            "ours": self.ours,
            "theirs": self.theirs,
            "delta": self.delta,
            "detail": self.detail,
        }


def _compare(
    *,
    rule_id: str,
    ours: float,
    theirs: float,
    tol: Tolerance,
    scope: str = "global",
    detail: dict | None = None,
) -> InvariantResult:
    sev = classify(ours=ours, theirs=theirs, tol=tol)
    return InvariantResult(
        rule_id=rule_id,
        severity=sev,
        scope=scope,
        ours=ours,
        theirs=theirs,
        delta=ours - theirs,
        detail=detail or {},
    )


def check_ov1_total_market_value(
    *,
    total_market_value: float,
    lots: Iterable[Any],
    tol: Tolerance,
) -> InvariantResult:
    """OV-1: Overview total_market_value == sum of per-lot market values."""
    expected = sum(lot.market_value for lot in lots)
    return _compare(
        rule_id="OV-1",
        ours=total_market_value,
        theirs=expected,
        tol=tol,
    )


def check_ov2_unrealized_consistency(
    *,
    total_market_value: float,
    total_basis: float,
    unrealized_pl: float,
    tol: Tolerance,
) -> InvariantResult:
    """OV-2: Overview unrealized_pl == total_market_value - total_basis."""
    expected = total_market_value - total_basis
    return _compare(
        rule_id="OV-2",
        ours=unrealized_pl,
        theirs=expected,
        tol=tol,
    )


def check_ov3_realized_ytd(
    *,
    realized_pl_ytd: float,
    closed_lots_ytd: Iterable[tuple[float, ...]],
    tol: Tolerance,
) -> InvariantResult:
    """OV-3: Overview realized_pl_ytd == sum of YTD closed-lot P&L.

    closed_lots_ytd is an iterable of (realized_pl,) tuples - using a tuple
    rather than a domain type keeps this function testable in isolation.
    """
    expected = sum(row[0] for row in closed_lots_ytd)
    return _compare(
        rule_id="OV-3",
        ours=realized_pl_ytd,
        theirs=expected,
        tol=tol,
    )


def check_al1_allocation_sums_to_100(
    *,
    allocation_rows: Iterable[tuple[str, float]],
    tol: Tolerance,
) -> InvariantResult:
    """AL-1: Allocation %s sum to 100.00 +/- tolerance."""
    total = sum(pct for _sym, pct in allocation_rows)
    return _compare(rule_id="AL-1", ours=total, theirs=100.0, tol=tol)


def check_al2_leaderboard_weight(
    *,
    leaderboard_rows: Iterable[tuple[str, float]],
    total_market_value: float,
    tol: Tolerance,
) -> InvariantResult:
    """AL-2: Allocation leaderboard total weight == total_market_value."""
    leaderboard_total = sum(weight for _sym, weight in leaderboard_rows)
    return _compare(
        rule_id="AL-2",
        ours=leaderboard_total,
        theirs=total_market_value,
        tol=tol,
    )


def check_pl1_value_consistency(
    *,
    lot_rows: Iterable[dict],
    tol: Tolerance,
) -> list[InvariantResult]:
    """PL-1: Each per-lot row: qty x current_price ~= market_value."""
    out: list[InvariantResult] = []
    for row in lot_rows:
        expected = float(row["qty"]) * float(row["current_price"])
        out.append(
            _compare(
                rule_id="PL-1",
                ours=float(row["market_value"]),
                theirs=expected,
                tol=tol,
                scope=f"lot:{row['id']}",
            )
        )
    return out


def check_pl2_pnl_consistency(
    *,
    lot_rows: Iterable[dict],
    tol: Tolerance,
) -> list[InvariantResult]:
    """PL-2: Each per-lot row: market_value - adjusted_basis == unrealized_pl."""
    out: list[InvariantResult] = []
    for row in lot_rows:
        expected = float(row["market_value"]) - float(row["adjusted_basis"])
        out.append(
            _compare(
                rule_id="PL-2",
                ours=float(row["unrealized_pl"]),
                theirs=expected,
                tol=tol,
                scope=f"lot:{row['id']}",
            )
        )
    return out


def check_pl3_holding_period(
    *,
    lot_rows: Iterable[dict],
    today: _date,
) -> list[InvariantResult]:
    """PL-3: holding period bucket (ST/LT) matches today - tacked_acquired_date >= 366."""
    out: list[InvariantResult] = []
    for row in lot_rows:
        acquired = _date.fromisoformat(row["tacked_acquired_date"])
        days = (today - acquired).days
        expected_bucket = "LT" if days >= 366 else "ST"
        actual_bucket = row["bucket"]
        if actual_bucket == expected_bucket:
            sev = Severity.OK
            detail = {"days_held": days, "bucket": actual_bucket}
        else:
            sev = Severity.FAIL
            detail = {
                "days_held": days,
                "actual_bucket": actual_bucket,
                "expected_bucket": expected_bucket,
                "reason": f"expected {expected_bucket} after {days} days, got {actual_bucket}",
            }
        out.append(
            InvariantResult(
                rule_id="PL-3",
                severity=sev,
                scope=f"lot:{row['id']}",
                ours=None,
                theirs=None,
                delta=None,
                detail=detail,
            )
        )
    return out


def check_xp1_cross_page(
    *,
    positions_sum: float,
    cached_overview_total: float | None,
    tol: Tolerance,
) -> InvariantResult:
    """XP-1: Sum of /positions per-lot rows == Overview total_market_value.

    If the cache is empty/stale, this check is intentionally skipped (OK with
    a 'skipped' detail flag) rather than falsely flagging - the user simply
    hasn't visited the Overview page yet in this process lifetime.
    """
    if cached_overview_total is None:
        return InvariantResult(
            rule_id="XP-1",
            severity=Severity.OK,
            scope="cross_page",
            ours=None,
            theirs=None,
            delta=None,
            detail={"skipped": True, "reason": "no recent overview snapshot in cache"},
        )
    return _compare(
        rule_id="XP-1",
        ours=positions_sum,
        theirs=cached_overview_total,
        tol=tol,
        scope="cross_page",
    )
