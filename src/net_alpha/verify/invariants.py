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
