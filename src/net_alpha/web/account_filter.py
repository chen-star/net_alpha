"""Helper for parsing the multi-account URL filter."""

from __future__ import annotations


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
