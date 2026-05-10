"""Pairing visualization — pure transform mapping timeline rows to pairing fields.

A "pair" groups timeline rows that belong to the same logical position (an
option open/close cycle or a stock buy lot and its consuming sells). This
module is presentation-layer only: nothing here is persisted, and nothing
outside the ticker page consumes its output.

Spec: docs/superpowers/specs/2026-05-10-ticker-trade-pairings-design.md
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from net_alpha.models.domain import Lot

# Pairing accepts any object with .trade and .assigned_from attributes
# (duck typing) so this module avoids importing TimelineRow from
# routes/ticker.py and the resulting cycle.


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


PALETTE_SIZE = 8


def _color_idx(pair_key: str) -> int:
    """Stable 0..PALETTE_SIZE-1 from a pair_key. SHA-1 truncated for stability
    across Python versions (Python's built-in hash() is randomized per run)."""
    digest = hashlib.sha1(pair_key.encode("utf-8")).digest()
    return digest[0] % PALETTE_SIZE


_OPEN_OPT_SOURCES = {"option_short_open", "option_short_open_assigned"}
_CLOSE_OPT_SOURCES = {
    "option_short_close",
    "option_short_close_expiry",
    "option_short_close_assigned",
}
_ALL_OPT_SOURCES = _OPEN_OPT_SOURCES | _CLOSE_OPT_SOURCES


def _option_pair_key(trade) -> str | None:
    """Pair-key for short-option positions. Long options not paired in v1."""
    opt = trade.option_details
    if opt is None:
        return None
    if trade.basis_source not in _ALL_OPT_SOURCES:
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


def _apply_option_pairs(rows: list, out: dict[str, PairFields]) -> None:
    """Group option opens/closes by pair-key and write open/close PairFields."""
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


def _apply_stock_lot_pairs(
    rows: list,
    lots: list[Lot],
    open_lot_ids: set[str],
    out: dict[str, PairFields],
) -> None:
    """FIFO-attribute stock SELLs to lots and write open/close/still_open PairFields."""
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


def _apply_roll_annotations(rows: list, out: dict[str, PairFields]) -> None:
    """Annotate same-day option openers with the closed pair's key (roll detection)."""
    # On any date D for ticker T, if a close-side option pair has a
    # different-key open on the same date, annotate the new opener with
    # the closed pair's key.
    closes_by_date_ticker: dict[tuple, list[str]] = defaultdict(list)  # (date, account, ticker) -> [pair_key]
    for r in rows:
        if _is_option_close(r.trade):
            key = _option_pair_key(r.trade)
            if key is None:
                continue
            closes_by_date_ticker[(r.trade.date, r.trade.account, r.trade.ticker)].append(key)

    for r in rows:
        if not _is_option_open(r.trade):
            continue
        opener_key = _option_pair_key(r.trade)
        if opener_key is None:
            continue
        same_day_closes = closes_by_date_ticker.get((r.trade.date, r.trade.account, r.trade.ticker), [])
        candidates = sorted(k for k in same_day_closes if k != opener_key)
        if not candidates:
            continue
        prev = out.get(r.trade.id)
        if prev is None:
            continue
        # Replace the dataclass with a copy that sets roll_from_pair_key.
        out[r.trade.id] = PairFields(
            pair_key=prev.pair_key,
            pair_role=prev.pair_role,
            pair_color_idx=prev.pair_color_idx,
            pair_position=prev.pair_position,
            pair_cap=prev.pair_cap,
            partner_trade_id=prev.partner_trade_id,
            roll_from_pair_key=candidates[0],
            assignment_link=prev.assignment_link,
            multi_lot_overflow=prev.multi_lot_overflow,
        )


def _apply_assignment_links(
    rows: list,
    assignment_closes: list,
    out: dict[str, PairFields],
) -> None:
    """Cross-reference option assignment-closes with stock BUY rows."""
    # Index: option pair-key -> list of put_assignment / call-stock-sell trade rows.
    pa_rows_by_key: dict[str, list] = defaultdict(list)
    for r in rows:
        t = r.trade
        if t.basis_source == "put_assignment" and r.assigned_from is not None:
            af = r.assigned_from
            key = f"OPT|{t.account}|{t.ticker}|{af.strike}|{af.expiry.isoformat()}|{af.call_put}"
            pa_rows_by_key[key].append(r)

    # For each dropped assignment-close, find the matching STO and the
    # matching stock BUY and link them.
    for ac in assignment_closes:
        if ac.option_details is None:
            continue
        opt = ac.option_details
        key = f"OPT|{ac.account}|{ac.ticker}|{opt.strike}|{opt.expiry.isoformat()}|{opt.call_put}"
        sto_rows = [r for r in rows if _option_pair_key(r.trade) == key and _is_option_open(r.trade)]
        if not sto_rows:
            continue
        sto_row = sto_rows[0]
        target_buy_rows = pa_rows_by_key.get(key, [])
        if not target_buy_rows:
            continue
        target_id = target_buy_rows[0].trade.id

        prev = out.get(sto_row.trade.id)
        if prev is None:
            continue
        out[sto_row.trade.id] = PairFields(
            pair_key=prev.pair_key,
            pair_role="closed_via_assignment",
            pair_color_idx=prev.pair_color_idx,
            pair_position=prev.pair_position,
            pair_cap="top",  # close has no visible row, so only cap-top
            partner_trade_id=target_id,
            roll_from_pair_key=prev.roll_from_pair_key,
            assignment_link={"direction": "to_stock", "target_trade_id": target_id},
            multi_lot_overflow=prev.multi_lot_overflow,
        )

        # Annotate the stock BUY (overrides only assignment_link; preserves
        # whatever still_open / open / role the stock-lot block already set).
        prev_buy = out.get(target_id)
        if prev_buy is None:
            continue
        out[target_id] = PairFields(
            pair_key=prev_buy.pair_key,
            pair_role=prev_buy.pair_role,
            pair_color_idx=prev_buy.pair_color_idx,
            pair_position=prev_buy.pair_position,
            pair_cap=prev_buy.pair_cap,
            partner_trade_id=prev_buy.partner_trade_id,
            roll_from_pair_key=prev_buy.roll_from_pair_key,
            assignment_link={"direction": "from_option", "target_trade_id": sto_row.trade.id},
            multi_lot_overflow=prev_buy.multi_lot_overflow,
        )


def _with_colors(out: dict[str, PairFields]) -> dict[str, PairFields]:
    """Return a new dict with pair_color_idx set deterministically (skipped for still_open lots)."""
    out_with_colors: dict[str, PairFields] = {}
    for trade_id, pf in out.items():
        if pf.pair_role == "still_open" or pf.pair_key is None:
            out_with_colors[trade_id] = pf
            continue
        out_with_colors[trade_id] = PairFields(
            pair_key=pf.pair_key,
            pair_role=pf.pair_role,
            pair_color_idx=_color_idx(pf.pair_key),
            pair_position=pf.pair_position,
            pair_cap=pf.pair_cap,
            partner_trade_id=pf.partner_trade_id,
            roll_from_pair_key=pf.roll_from_pair_key,
            assignment_link=pf.assignment_link,
            multi_lot_overflow=pf.multi_lot_overflow,
        )
    return out_with_colors


def compute_pair_fields(
    *,
    timeline_rows: Iterable,
    lots: Iterable[Lot],
    open_lot_ids: set[str],
    assignment_closes: Iterable | None = None,
) -> dict[str, PairFields]:
    """Return per-trade pairing metadata keyed by trade.id."""
    rows = list(timeline_rows)
    assignment_closes_list = list(assignment_closes or [])
    if not rows and not assignment_closes_list:
        return {}

    out: dict[str, PairFields] = {}
    _apply_option_pairs(rows, out)
    _apply_stock_lot_pairs(rows, list(lots), open_lot_ids, out)
    _apply_roll_annotations(rows, out)
    _apply_assignment_links(rows, assignment_closes_list, out)
    return _with_colors(out)
