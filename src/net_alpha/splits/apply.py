from __future__ import annotations

from datetime import date

from net_alpha.db.repository import Repository


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
