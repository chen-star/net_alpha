"""Helper for parsing the multi-account URL filter."""

from __future__ import annotations

# Synthetic FK placeholder created by Repository.save_broker_positions for
# positions-CSV imports (broker="positions", label="(multi)"). It holds no
# trades and must never appear as a selectable trading account in pickers.
POSITIONS_SENTINEL_DISPLAY = "positions/(multi)"


def exclude_positions_sentinel(displays: list[str]) -> list[str]:
    """Drop the positions-snapshot sentinel from a list of account displays,
    preserving order. Used to keep it out of trade/scope account pickers."""
    return [d for d in displays if d != POSITIONS_SENTINEL_DISPLAY]


def parse_accounts(raw: list[str]) -> list[str]:
    """Normalize the FastAPI-parsed `account` query list.

    - Strips whitespace.
    - Drops empty strings (matches the historical `?account=` "All accounts" form).
    - Dedupes while preserving first-seen order.

    An empty result means "no filter / all accounts".
    """
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        s = (item or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out
