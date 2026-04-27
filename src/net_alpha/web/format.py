"""Pure presentation helpers for web templates."""

from __future__ import annotations

from net_alpha.models.domain import Trade


def display_action(t: Trade) -> str:
    """User-facing action label.

    Transfers are stored as Buy/Sell with basis_source set to transfer_in /
    transfer_out so engine logic treats them uniformly. The Timeline column
    re-expands the label for clarity.
    """
    if t.basis_source == "transfer_in":
        return "Transfer In"
    if t.basis_source == "transfer_out":
        return "Transfer Out"
    return t.action
