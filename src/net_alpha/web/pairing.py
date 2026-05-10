"""Pairing visualization — pure transform mapping timeline rows to pairing fields.

A "pair" groups timeline rows that belong to the same logical position (an
option open/close cycle or a stock buy lot and its consuming sells). This
module is presentation-layer only: nothing here is persisted, and nothing
outside the ticker page consumes its output.

Spec: docs/superpowers/specs/2026-05-10-ticker-trade-pairings-design.md
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from net_alpha.models.domain import Lot

# Forward reference to avoid an import cycle with routes/ticker.py
# where TimelineRow is defined.
TimelineRow = "net_alpha.web.routes.ticker.TimelineRow"


PairRole = Literal["open", "close", "still_open", "closed_via_assignment"]
PairCap = Literal["top", "bottom", "both", "none"]


@dataclass(frozen=True)
class PairFields:
    """Computed pairing metadata for a single timeline row."""

    pair_key: str | None = None
    pair_role: PairRole | None = None
    pair_color_idx: int | None = None
    pair_position: tuple[int, int] | None = None
    pair_cap: PairCap | None = None
    partner_trade_id: str | None = None  # for jump-to-partner
    roll_from_pair_key: str | None = None
    assignment_link: dict | None = None
    multi_lot_overflow: int = 0  # SELLs spanning multiple lots: count of extra lots


def compute_pair_fields(
    *,
    timeline_rows: Iterable,
    lots: Iterable[Lot],
    open_lot_ids: set[str],
) -> dict[str, PairFields]:
    """Return per-trade pairing metadata keyed by trade.id.

    Empty input yields an empty dict. Real implementation built incrementally
    in subsequent tasks.
    """
    rows = list(timeline_rows)
    if not rows:
        return {}
    return {}  # filled in by later tasks
