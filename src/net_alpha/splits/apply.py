from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import TYPE_CHECKING

from net_alpha.db.repository import Repository

if TYPE_CHECKING:
    from net_alpha.models.splits import LotOverride


def apply_splits(repo: Repository) -> int:
    """Mutate every persisted lot whose date < a known split's ex-date by
    multiplying quantity by the split ratio. adjusted_basis is preserved
    (basis is dollars, not per-share). Writes a lot_overrides row per
    mutation, keyed by (trade_id, split_id), for idempotency.

    Returns the count of lot mutations applied (0 on a steady state).
    """
    splits = repo.get_splits()  # all symbols
    if not splits:
        return 0

    mutations = 0
    for split in splits:
        lots = repo.get_lot_rows_for_symbol(split.symbol)
        for lot in lots:
            lot_date = date.fromisoformat(lot["trade_date"])
            if lot_date >= split.split_date:
                continue  # lot is already post-split
            existing = repo.get_split_overrides_for_trade(int(lot["trade_id"]), int(split.id))
            if existing:
                continue  # already applied
            old_qty = float(lot["quantity"])
            new_qty = old_qty * split.ratio
            old_basis = float(lot["adjusted_basis"])
            # Mutate the lot row.
            repo.update_lot_qty_and_basis(
                int(lot["id"]),
                quantity=new_qty,
                adjusted_basis=old_basis,  # unchanged
            )
            # Audit row.
            repo.add_lot_override(
                trade_id=int(lot["trade_id"]),
                field="quantity",
                old_value=old_qty,
                new_value=new_qty,
                reason="split",
                split_id=int(split.id),
            )
            mutations += 1
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
