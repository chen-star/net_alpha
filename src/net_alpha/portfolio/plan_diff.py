"""Pure-function diff for the Plan view's "what changed since last open"
badges. Reads only structured row inputs — no Repository, no I/O.

Spec: docs/superpowers/specs/2026-05-10-palette-and-table-ergonomics-design.md
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

# Bucket thresholds for unrealized P&L. A row's bucket is the floor of
# `unrealized_pl / step`, where `step` is the *wider* of the two:
#   - $250 (absolute floor — small lots)
#   - 5% × |basis| (proportional — large lots)
# Using the wider step makes the bucket coarser, so $0.03 jitter never
# crosses a boundary.
PL_DOLLAR_STEP: int = 250
PL_PCT_STEP: float = 0.05

ChangeState = Literal["new", "changed"]


@dataclass(frozen=True, slots=True)
class PlanDiffRow:
    ticker: str
    target_kind: str  # "shares" | "usd"
    target_value: float
    risk_pill: str  # "green" | "yellow" | "red"
    pl_bucket: int  # see compute_pl_bucket


@dataclass(frozen=True, slots=True)
class SnapshotRow:
    ticker: str
    target_kind: str
    target_value: float
    risk_pill: str
    pl_bucket: int


def compute_pl_bucket(unrealized_pl: float, basis: float) -> int:
    """Coarse signed bin of unrealized P&L. See module docstring."""
    step = max(float(PL_DOLLAR_STEP), abs(basis) * PL_PCT_STEP)
    if step == 0:
        return 0
    return math.floor(unrealized_pl / step)


def diff_plan(
    current_rows: list[PlanDiffRow],
    snapshot_rows: dict[str, SnapshotRow],
) -> dict[str, ChangeState | None]:
    """Per-ticker change_state.

    Tickers in `snapshot_rows` but absent from `current_rows` are NOT
    included in the result — the row is not on screen to badge.
    """
    out: dict[str, ChangeState | None] = {}
    for row in current_rows:
        snap = snapshot_rows.get(row.ticker)
        if snap is None:
            out[row.ticker] = "new"
            continue
        # Risk-pill tier change always counts as "changed".
        if row.risk_pill != snap.risk_pill:
            out[row.ticker] = "changed"
            continue
        if (
            row.target_kind != snap.target_kind
            or row.target_value != snap.target_value
            or row.pl_bucket != snap.pl_bucket
        ):
            out[row.ticker] = "changed"
            continue
        out[row.ticker] = None
    return out
