"""Pure presentation helpers for web templates."""

from __future__ import annotations

from net_alpha.models.domain import OptionDetails, Trade


def _format_option_suffix(opt: OptionDetails) -> str:
    """e.g. 'CALL $400 06/18/26' — compact, dense, sortable-readable."""
    cp = "CALL" if opt.call_put == "C" else "PUT"
    strike = f"${opt.strike:g}"
    expiry = opt.expiry.strftime("%m/%d/%y")
    return f"{cp} {strike} {expiry}"


def display_action(t: Trade) -> str:
    """User-facing action label.

    Transfers are stored as Buy/Sell with basis_source set to transfer_in /
    transfer_out so engine logic treats them uniformly. The Timeline column
    re-expands the label for clarity. Option trades are extended with the
    contract details (CALL/PUT, strike, expiry) so the user can tell at a
    glance whether a row is stock or an option position.
    """
    if t.basis_source == "transfer_in":
        return "Transfer In"
    if t.basis_source == "transfer_out":
        return "Transfer Out"
    if t.basis_source == "option_short_open_assigned" and t.option_details is not None:
        return f"Sell to Open {_format_option_suffix(t.option_details)} (assigned)"
    if t.basis_source == "option_short_close_assigned" and t.option_details is not None:
        return f"Closed by Assignment {_format_option_suffix(t.option_details)}"
    if t.option_details is not None:
        if t.basis_source == "option_short_open":
            return f"Sell to Open {_format_option_suffix(t.option_details)}"
        if t.basis_source == "option_short_close":
            return f"Buy to Close {_format_option_suffix(t.option_details)}"
        return f"{t.action} {_format_option_suffix(t.option_details)}"
    return t.action
