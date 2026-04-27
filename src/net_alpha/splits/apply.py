from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import TYPE_CHECKING

from net_alpha.db.repository import Repository

if TYPE_CHECKING:
    from net_alpha.models.splits import LotOverride


def apply_splits(repo: Repository) -> int:
    """Set every lot's quantity to its trade's original quantity multiplied by
    the cumulative product of all splits whose ex-date is after the trade's
    date. Idempotent by construction: lot.quantity is always derived from
    canonical inputs (the trade's original quantity + the splits table), so
    calling apply_splits N times produces the same result as calling it once.

    The lot_overrides table is written as an AUDIT log (one row per (trade,
    split) the first time a non-trivial multiplier is recorded), but is NOT
    consulted to gate the mutation. This is the key fix: before, an existing
    override row would short-circuit and leave a freshly-regenerated raw lot
    un-adjusted (the bug: after Sync Splits + any subsequent import, SQQQ
    would silently revert from 10 shares back to 100).

    Returns the count of lot mutations actually applied (i.e., where the
    target quantity differed from the lot's current quantity).
    """
    splits = repo.get_splits()
    if not splits:
        return 0

    by_symbol: dict[str, list] = defaultdict(list)
    for s in splits:
        by_symbol[s.symbol].append(s)

    mutations = 0
    for symbol, sym_splits in by_symbol.items():
        lots = repo.get_lot_rows_for_symbol(symbol)
        for lot in lots:
            lot_date = date.fromisoformat(lot["trade_date"])

            cumulative = 1.0
            applicable_splits: list = []
            for sp in sym_splits:
                if sp.split_date > lot_date:
                    cumulative *= sp.ratio
                    applicable_splits.append(sp)

            if cumulative == 1.0:
                continue  # no splits affect this lot

            # Canonical formula: lot's target quantity is the ORIGINAL buy
            # quantity (carried by the trade row, never mutated) times the
            # cumulative ratio of all post-buy splits.
            trade = repo.get_trade_by_id(int(lot["trade_id"]))
            if trade is None:
                continue
            target_qty = float(trade.quantity) * cumulative
            current_qty = float(lot["quantity"])
            current_basis = float(lot["adjusted_basis"])

            if target_qty == current_qty:
                continue  # already split-adjusted; no mutation needed

            repo.update_lot_qty_and_basis(
                int(lot["id"]),
                quantity=target_qty,
                adjusted_basis=current_basis,  # unchanged; basis is dollars
            )
            mutations += 1

            # Write audit rows for splits we haven't recorded for this trade
            # before. Idempotent: skips if an override row already exists for
            # this (trade_id, split_id).
            for sp in applicable_splits:
                if not repo.get_split_overrides_for_trade(int(lot["trade_id"]), int(sp.id)):
                    repo.add_lot_override(
                        trade_id=int(lot["trade_id"]),
                        field="quantity",
                        old_value=current_qty,
                        new_value=target_qty,
                        reason="split",
                        split_id=int(sp.id),
                    )

    return mutations


def apply_manual_overrides(repo: Repository) -> int:
    """Re-apply ANY 'manual' lot_overrides row to the corresponding lot,
    keyed by trade_id. Idempotent — applies the LATEST manual override per
    (trade_id, field). Returns count of mutations actually written."""
    overrides = repo.all_lot_overrides()
    if not overrides:
        return 0

    # Latest-wins per (trade_id, field) for reason='manual'.
    latest: dict[tuple[int, str], LotOverride] = {}
    for o in overrides:
        if o.reason != "manual":
            continue
        key = (o.trade_id, o.field)
        prev = latest.get(key)
        if prev is None or o.edited_at > prev.edited_at:
            latest[key] = o

    if not latest:
        return 0

    # Group by trade_id so we read each lot once.
    by_trade: dict[int, list] = defaultdict(list)
    for (tid, _field), o in latest.items():
        by_trade[tid].append(o)

    mutations = 0
    for tid, applicable in by_trade.items():
        lot = repo.get_lot_row_dict_by_trade_id(tid)
        if lot is None:
            continue
        new_qty = float(lot["quantity"])
        new_basis = float(lot["adjusted_basis"])
        for o in applicable:
            if o.field == "quantity":
                new_qty = o.new_value
            elif o.field == "adjusted_basis":
                new_basis = o.new_value
        if new_qty != lot["quantity"] or new_basis != lot["adjusted_basis"]:
            repo.update_lot_qty_and_basis(int(lot["id"]), quantity=new_qty, adjusted_basis=new_basis)
            mutations += 1
    return mutations
