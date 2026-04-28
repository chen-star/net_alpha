"""Forward lockout-clear-date computation for the harvest queue and traffic light.

A symbol is "in lockout" if a closing sale at a loss today would trigger a wash-sale
violation under IRS Pub 550 §1091. The lockout-clear date is the first date on which
such a sale would be safe given the most recent qualifying buy in the past 30 days.
"""

from __future__ import annotations

from datetime import date, timedelta

from net_alpha.models.domain import Trade

WASH_SALE_WINDOW_DAYS = 30
_BUY_ACTIONS = {"Buy", "Buy to Open"}


def _substantially_identical(symbol: str, etf_pairs: dict[str, list[str]]) -> set[str]:
    """Symbols treated as substantially identical to *symbol* per etf_pairs."""
    related = {symbol}
    for group_members in etf_pairs.values():
        if symbol in group_members:
            related.update(group_members)
    return related


def compute_lockout_clear_date(
    symbol: str,
    account: str,
    all_trades: list[Trade],
    as_of: date,
    etf_pairs: dict[str, list[str]],
) -> date | None:
    """Earliest date a sale of *symbol* in *account* will be wash-sale-clear.

    Returns None when no qualifying buy in the past 30 days exists (already clear).

    Cross-account buys also lock out (wash-sale rules apply across the taxpayer's
    accounts). Substantially-identical symbols (per etf_pairs) extend the lockout.
    """
    # account is intentionally unused: wash-sale rules apply across all of the
    # taxpayer's accounts, so we scan all_trades regardless of account.
    _ = account

    related = _substantially_identical(symbol, etf_pairs)
    cutoff = as_of - timedelta(days=WASH_SALE_WINDOW_DAYS)

    most_recent: date | None = None
    for t in all_trades:
        if t.action not in _BUY_ACTIONS:
            continue
        if t.option_details is not None:
            continue  # option opens handled by the cross-asset extension (Task 6).
        if t.ticker not in related:
            continue
        if t.date < cutoff or t.date > as_of:
            continue
        if most_recent is None or t.date > most_recent:
            most_recent = t.date

    if most_recent is None:
        return None
    return most_recent + timedelta(days=WASH_SALE_WINDOW_DAYS + 1)
