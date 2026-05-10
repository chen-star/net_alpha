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


def _is_stock_buy(trade) -> bool:
    return trade.option_details is None and trade.action.lower() == "buy"


def _is_stock_sell(trade) -> bool:
    return trade.option_details is None and trade.action.lower() == "sell"


def _attribute_sells_to_lots(rows, lots):
    """FIFO walk: for each stock SELL, return [(lot_id, qty_consumed), ...].

    Replicates the consume_lots_fifo grouping locally because that helper
    aggregates remaining qty per lot but doesn't expose per-SELL attribution.
    """
    # Group lots by (account, ticker), oldest first.
    lots_by_key: dict[tuple[str, str], list[Lot]] = defaultdict(list)
    for lot in lots:
        if lot.option_details is not None:
            continue
        lots_by_key[(lot.account, lot.ticker)].append(lot)
    for group in lots_by_key.values():
        group.sort(key=lambda lt: lt.date)

    # Per-lot remaining qty as we walk SELLs.
    remaining: dict[str, float] = {lot.id: float(lot.quantity) for lot in lots if lot.option_details is None}

    sell_rows = sorted(
        (r for r in rows if _is_stock_sell(r.trade)),
        key=lambda r: r.trade.date,
    )

    attribution: dict[str, list[tuple[str, float]]] = {}
    for r in sell_rows:
        t = r.trade
        key = (t.account, t.ticker)
        to_take = float(t.quantity)
        consumed: list[tuple[str, float]] = []
        for lot in lots_by_key.get(key, []):
            if to_take <= 0:
                break
            avail = remaining.get(lot.id, 0.0)
            if avail <= 0:
                continue
            take = min(avail, to_take)
            remaining[lot.id] = avail - take
            consumed.append((lot.id, take))
            to_take -= take
        attribution[t.id] = consumed
    return attribution


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

    # --- Stock lot pairs ---
    lots_list = [lot for lot in lots if lot.option_details is None]
    lots_by_id = {lot.id: lot for lot in lots_list}
    sell_attribution = _attribute_sells_to_lots(rows, lots_list)

    # Index: lot_id -> [opening BUY row, closing SELL rows (in date order)]
    lot_open_row: dict[str, object] = {}
    lot_close_rows: dict[str, list] = defaultdict(list)

    # Match each BUY trade row to its lot via lot.trade_id == trade.id.
    buy_to_lot: dict[str, str] = {lot.trade_id: lot.id for lot in lots_list}
    for r in rows:
        if _is_stock_buy(r.trade) and r.trade.id in buy_to_lot:
            lot_open_row[buy_to_lot[r.trade.id]] = r

    # Each SELL goes to its primary lot (largest contribution).
    sell_primary_lot: dict[str, tuple[str, int]] = {}
    for r in rows:
        if not _is_stock_sell(r.trade):
            continue
        contributions = sell_attribution.get(r.trade.id, [])
        if not contributions:
            continue  # SELL with no lot to pair (shouldn't happen post-FIFO; skip)
        contributions_sorted = sorted(contributions, key=lambda c: c[1], reverse=True)
        primary_lot_id, _ = contributions_sorted[0]
        overflow = max(0, len(contributions_sorted) - 1)
        sell_primary_lot[r.trade.id] = (primary_lot_id, overflow)
        lot_close_rows[primary_lot_id].append(r)

    for lot_id, lot in lots_by_id.items():
        open_row = lot_open_row.get(lot_id)
        if open_row is None:
            continue  # lot's opening BUY not in this row set
        closes = sorted(lot_close_rows.get(lot_id, []), key=lambda r: r.trade.date)
        is_still_open = lot_id in open_lot_ids
        key = f"LOT|{lot_id}"

        first_close_id = closes[0].trade.id if closes else None

        if is_still_open:
            out[open_row.trade.id] = PairFields(
                pair_key=key,
                pair_role="still_open",
                pair_cap="top",
                partner_trade_id=None,
            )
        else:
            out[open_row.trade.id] = PairFields(
                pair_key=key,
                pair_role="open",
                pair_cap="top",
                pair_position=(1, 1),
                partner_trade_id=first_close_id,
            )

        for i, r in enumerate(closes, start=1):
            _, overflow = sell_primary_lot[r.trade.id]
            cap = "bottom" if (i == len(closes) and not is_still_open) else "none"
            out[r.trade.id] = PairFields(
                pair_key=key,
                pair_role="close",
                pair_position=(i, len(closes)) if len(closes) > 1 else (1, 1),
                pair_cap=cap,
                partner_trade_id=open_row.trade.id,
                multi_lot_overflow=overflow,
            )

    return out
