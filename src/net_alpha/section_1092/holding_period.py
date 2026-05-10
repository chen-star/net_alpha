"""§1092(f) holding-period suspension warnings.

Pure function. Takes the detector's OffsettingGroup output and emits one
HoldingPeriodSuspension per long lot that is currently part of a straddle.

v1 emits warnings only — no basis adjustment, no LT→ST reclassification.
The user is informed; their tax software / CPA does the actual filing.
"""

from __future__ import annotations

from collections.abc import Iterable

from net_alpha.models.domain import HoldingPeriodSuspension, OffsettingGroup


def compute_suspensions(
    groups: Iterable[OffsettingGroup],
) -> list[HoldingPeriodSuspension]:
    """One suspension record per long leg whose holding-period clock predates the offset.

    A long leg opened strictly before the latest leg-open date in the group
    had its LT clock running before the straddle existed; §1092(f) freezes
    that clock. A leg opened on the same date as the offset's creation has
    no prior clock to suspend, so we skip it. Short legs and legs with no
    lot_id are also skipped (no LT clock to track in v1).
    """
    out: list[HoldingPeriodSuspension] = []
    for g in groups:
        long_legs = [p for p in g.positions if p.side == "long"]
        if not long_legs:
            continue
        # Suspension begins on the LATER of the two leg-open dates — that is,
        # when the offsetting relationship was first established. Resumed_at is
        # always None in v1 (we look at currently-open groups; closures are out
        # of scope until v2 ships persisted suspension history).
        suspension_start = max(p.opened_at for p in g.positions)

        # Only suspend legs whose holding-period clock had already started
        # running before the offset was created — i.e., legs opened strictly
        # before suspension_start. A leg opened on suspension_start has nothing
        # to suspend (its clock starts at the same moment the offset begins).
        # Pick a representative offsetting-leg kind for diagnostic display.
        # For each long leg, the offsetting kind is the *other* side's kind.
        for leg in long_legs:
            if leg.lot_id is None:
                continue  # cannot suspend a position we can't pin to a lot
            if leg.opened_at >= suspension_start:
                continue  # no prior holding-period clock to suspend
            other = next((p for p in g.positions if p is not leg), None)
            if other is None:
                continue
            out.append(
                HoldingPeriodSuspension(
                    account=g.account,
                    ticker=g.ticker,
                    lot_id=leg.lot_id,
                    suspended_at=suspension_start,
                    resumed_at=None,
                    offsetting_position_kind=other.kind,
                    rule_citation="IRC §1092(f)",
                )
            )
    return out
