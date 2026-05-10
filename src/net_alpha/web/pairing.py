"""Pairing visualization — pure transform mapping timeline rows to pairing fields.

A "pair" groups timeline rows that belong to the same logical position (an
option open/close cycle or a stock buy lot and its consuming sells). This
module is presentation-layer only: nothing here is persisted, and nothing
outside the ticker page consumes its output.

Spec: docs/superpowers/specs/2026-05-10-ticker-trade-pairings-design.md
"""
from __future__ import annotations

from collections import defaultdict
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


_OPEN_OPT_SOURCES = {"option_short_open", "option_short_open_assigned"}
_CLOSE_OPT_SOURCES = {
    "option_short_close",
    "option_short_close_expiry",
    "option_short_close_assigned",
}


def _option_pair_key(trade) -> str | None:
    """Pair-key for short-option positions. Long options not paired in v1."""
    opt = trade.option_details
    if opt is None:
        return None
    if trade.basis_source not in _OPEN_OPT_SOURCES | _CLOSE_OPT_SOURCES:
        return None
    return f"OPT|{trade.account}|{trade.ticker}|{opt.strike}|{opt.expiry.isoformat()}|{opt.call_put}"


def _is_option_open(trade) -> bool:
    return trade.basis_source in _OPEN_OPT_SOURCES


def _is_option_close(trade) -> bool:
    return trade.basis_source in _CLOSE_OPT_SOURCES


def compute_pair_fields(
    *,
    timeline_rows: Iterable,
    lots: Iterable[Lot],
    open_lot_ids: set[str],
) -> dict[str, PairFields]:
    """Return per-trade pairing metadata keyed by trade.id."""
    rows = list(timeline_rows)
    if not rows:
        return {}

    out: dict[str, PairFields] = {}

    # --- Option pairs ---
    opt_groups: dict[str, list] = defaultdict(list)
    for r in rows:
        key = _option_pair_key(r.trade)
        if key is not None:
            opt_groups[key].append(r)

    for key, group in opt_groups.items():
        opens = [r for r in group if _is_option_open(r.trade)]
        closes = [r for r in group if _is_option_close(r.trade)]
        opens.sort(key=lambda r: r.trade.date)
        closes.sort(key=lambda r: r.trade.date)
        first_open_id = opens[0].trade.id if opens else None
        first_close_id = closes[0].trade.id if closes else None

        for i, r in enumerate(opens, start=1):
            cap: PairCap
            if i == 1:
                cap = "top"
            else:
                cap = "none"
            out[r.trade.id] = PairFields(
                pair_key=key,
                pair_role="open",
                pair_position=(i, len(opens)) if len(opens) > 1 else (1, 1),
                pair_cap=cap,
                partner_trade_id=first_close_id,
            )
        for i, r in enumerate(closes, start=1):
            cap = "bottom" if i == len(closes) else "none"
            out[r.trade.id] = PairFields(
                pair_key=key,
                pair_role="close",
                pair_position=(i, len(closes)) if len(closes) > 1 else (1, 1),
                pair_cap=cap,
                partner_trade_id=first_open_id,
            )

    return out
