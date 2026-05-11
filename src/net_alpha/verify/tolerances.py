"""Tolerance constants & config loader for the verification engine.

The 10× warn/fail split exists so small Schwab quirks flag as ⚠
without screaming while large drifts escalate.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml


class Severity(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"
    STALE = "stale"


@dataclass(frozen=True)
class Tolerance:
    """Per-comparison tolerance. Pass if |delta| <= max(abs, |theirs|*rel)."""

    abs: float
    rel: float


@dataclass(frozen=True)
class ToleranceConfig:
    invariants: Tolerance  # internal invariants (OV-*, AL-*, PL-*, XP-1)
    realized: Tolerance  # broker realized G/L
    positions_qty: Tolerance  # broker open positions: qty (exact)
    positions_basis: Tolerance  # broker open positions: cost basis
    positions_mv: Tolerance  # broker open positions: market value


# Defaults. Comments explain *why*.
_DEFAULTS = ToleranceConfig(
    # We control both sides; >$0.01 is a bug.
    invariants=Tolerance(abs=0.01, rel=0.0001),
    # Schwab compounds rounding across partial fills.
    realized=Tolerance(abs=0.50, rel=0.001),
    # Qty must match exactly — drift is always a real bug.
    positions_qty=Tolerance(abs=0.0, rel=0.0),
    # Aggregate basis carries lot-level wash-sale rounding we don't see.
    positions_basis=Tolerance(abs=1.00, rel=0.001),
    # Different intraday quote snapshots dominate this delta.
    positions_mv=Tolerance(abs=5.00, rel=0.005),
)


def classify(*, ours: float, theirs: float, tol: Tolerance) -> Severity:
    """Decide pass/warn/fail for one comparison."""
    delta = abs(ours - theirs)
    threshold = max(tol.abs, abs(theirs) * tol.rel)
    if delta <= threshold:
        return Severity.OK
    if delta <= 10 * threshold:
        return Severity.WARN
    return Severity.FAIL


def _config_path() -> Path:
    base = os.environ.get("NET_ALPHA_DIR") or str(Path.home() / ".net_alpha")
    return Path(base) / "config.yaml"


_FIELD_TO_TOL = {
    "invariants_abs": ("invariants", "abs"),
    "invariants_rel": ("invariants", "rel"),
    "realized_abs": ("realized", "abs"),
    "realized_rel": ("realized", "rel"),
    "positions_qty_abs": ("positions_qty", "abs"),
    "positions_qty_rel": ("positions_qty", "rel"),
    "positions_basis_abs": ("positions_basis", "abs"),
    "positions_basis_rel": ("positions_basis", "rel"),
    "positions_mv_abs": ("positions_mv", "abs"),
    "positions_mv_rel": ("positions_mv", "rel"),
}


def load_tolerances() -> ToleranceConfig:
    """Load defaults from above, apply overrides from ~/.net_alpha/config.yaml."""
    path = _config_path()
    if not path.exists():
        return _DEFAULTS
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        return _DEFAULTS
    overrides = (raw.get("verify") or {}).get("tolerances") or {}
    if not isinstance(overrides, dict):
        return _DEFAULTS
    # Build a mutable nested dict to apply overrides without mutating dataclasses.
    mut = {
        "invariants": {"abs": _DEFAULTS.invariants.abs, "rel": _DEFAULTS.invariants.rel},
        "realized": {"abs": _DEFAULTS.realized.abs, "rel": _DEFAULTS.realized.rel},
        "positions_qty": {"abs": _DEFAULTS.positions_qty.abs, "rel": _DEFAULTS.positions_qty.rel},
        "positions_basis": {"abs": _DEFAULTS.positions_basis.abs, "rel": _DEFAULTS.positions_basis.rel},
        "positions_mv": {"abs": _DEFAULTS.positions_mv.abs, "rel": _DEFAULTS.positions_mv.rel},
    }
    for key, value in overrides.items():
        if key in _FIELD_TO_TOL and isinstance(value, (int, float)):
            grp, attr = _FIELD_TO_TOL[key]
            mut[grp][attr] = float(value)
    return ToleranceConfig(
        invariants=Tolerance(**mut["invariants"]),
        realized=Tolerance(**mut["realized"]),
        positions_qty=Tolerance(**mut["positions_qty"]),
        positions_basis=Tolerance(**mut["positions_basis"]),
        positions_mv=Tolerance(**mut["positions_mv"]),
    )
