"""⌘K palette index — pure builder for the JSON blob bootstrapped into
every page render. Filtering happens client-side in static/palette.js;
this module produces only the data.
"""

from __future__ import annotations

from typing import Literal, Protocol, TypedDict


class _PageEntry(TypedDict, total=False):
    label: str
    route: str
    aliases: list[str]


class _TickerEntry(TypedDict):
    sym: str
    tier: Literal["held", "targeted", "traded"]


class _PaletteRepo(Protocol):
    def list_distinct_tickers(self) -> list[str]: ...
    def tickers_with_open_lots(self) -> set[str]: ...
    def distinct_target_tickers(self) -> list[str]: ...


# Declared once; the palette renders these verbatim. Aliases support fuzzy
# matches like "dashboard" → /, "harvest" → /tax. Empty `aliases` is fine.
PAGES: list[_PageEntry] = [
    {"label": "Portfolio", "route": "/", "aliases": ["dashboard", "home", "overview"]},
    {"label": "Positions", "route": "/positions", "aliases": ["holdings", "plan"]},
    {"label": "Sim", "route": "/sim", "aliases": ["simulator", "what-if"]},
    {"label": "Tax", "route": "/tax", "aliases": ["harvest", "performance"]},
    {"label": "Imports", "route": "/imports", "aliases": ["upload", "csv"]},
    {"label": "Settings", "route": "/settings", "aliases": ["preferences"]},
    {"label": "Carryforward", "route": "/settings/carryforward", "aliases": ["loss-carry"]},
    {"label": "Service", "route": "/settings/service", "aliases": ["launchd", "background"]},
]


def build_palette_index(repo: _PaletteRepo) -> dict:
    """Build the JSON-serializable palette index.

    Tier preference: held > targeted > traded. One ticker maps to exactly
    one tier. Tickers are sorted alphabetically; the client-side matcher
    re-sorts by score × tier multiplier.
    """
    held = set(repo.tickers_with_open_lots())
    targeted = set(repo.distinct_target_tickers())
    all_tickers = sorted(repo.list_distinct_tickers())

    tickers: list[_TickerEntry] = []
    for sym in all_tickers:
        if sym in held:
            tier: Literal["held", "targeted", "traded"] = "held"
        elif sym in targeted:
            tier = "targeted"
        else:
            tier = "traded"
        tickers.append({"sym": sym, "tier": tier})

    return {"pages": PAGES, "tickers": tickers}
