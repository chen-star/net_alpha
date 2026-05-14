"""Per-profile Overview page row order + hidden set.

Pure module: no DB, no IO. The Repository wraps these with SQLite reads.
"""

from __future__ import annotations

from pydantic import BaseModel

KNOWN_ROWS: tuple[str, ...] = (
    "inbox",
    "kpis",
    "curves",
    "monthly_pl",
    "allocation",
    "top_movers",
)


class OverviewLayout(BaseModel):
    model_config = {"extra": "ignore"}

    rows: list[str]
    hidden: list[str]


def default_overview_layout() -> OverviewLayout:
    return OverviewLayout(rows=list(KNOWN_ROWS), hidden=[])


def sanitize(raw: OverviewLayout) -> OverviewLayout:
    """Return a layout safe to store + render.

    - `rows` keeps only KNOWN_ROWS, deduped, in the order they appear.
    - Any KNOWN_ROWS missing from `rows` are appended at the end in canonical
      order (forward-compat when a new row key is introduced).
    - `hidden` is filtered against KNOWN_ROWS.
    """
    seen: set[str] = set()
    rows: list[str] = []
    for key in raw.rows:
        if key in KNOWN_ROWS and key not in seen:
            rows.append(key)
            seen.add(key)
    for key in KNOWN_ROWS:
        if key not in seen:
            rows.append(key)
    hidden = [k for k in raw.hidden if k in KNOWN_ROWS]
    return OverviewLayout(rows=rows, hidden=hidden)
