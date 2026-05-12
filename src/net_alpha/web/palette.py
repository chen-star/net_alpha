"""⌘K palette index — pure builder for the JSON blob bootstrapped into
every page render. Filtering happens client-side in static/palette.js;
this module produces only the data.
"""

from __future__ import annotations

from typing import Literal, Protocol, TypedDict


class _PageEntryRequired(TypedDict):
    label: str
    route: str


class _PageEntry(_PageEntryRequired, total=False):
    aliases: list[str]


class _TickerEntry(TypedDict):
    sym: str
    tier: Literal["held", "targeted", "traded"]


class _ActionEntry(TypedDict):
    """A verb-form palette row that pre-fills the sim form for a held symbol.

    Rendered as e.g. "Sim sell AAPL" and routes to
    ``/sim?ticker=AAPL&action=sell``. Only emitted for symbols the user
    currently holds — buying/selling something they don't own goes through
    the regular ticker → /sim navigation path.
    """

    label: str
    route: str
    verb: Literal["sell", "buy"]
    sym: str


class _FindingEntry(TypedDict):
    """A row from the latest verify run, surfaced for quick navigation.

    All findings link to ``/verify``; the palette match score does the
    work of letting the user type a rule_id or a scope fragment.
    """

    label: str
    route: str
    rule_id: str
    scope: str
    severity: str


class _PaletteRepo(Protocol):
    def list_distinct_tickers(self) -> list[str]: ...
    def tickers_with_open_lots(self) -> set[str]: ...
    def distinct_target_tickers(self) -> list[str]: ...
    def latest_verify_run(self): ...
    def list_verify_findings(self, *, run_id: int) -> list: ...


# Declared once; the palette renders these verbatim. Aliases support fuzzy
# matches like "dashboard" → /, "harvest" → /tax. Empty `aliases` is fine.
PAGES: list[_PageEntry] = [
    {"label": "Portfolio", "route": "/", "aliases": ["dashboard", "home", "overview"]},
    {"label": "Positions", "route": "/positions", "aliases": ["holdings", "plan"]},
    {"label": "Sim", "route": "/sim", "aliases": ["simulator", "what-if"]},
    {"label": "Tax", "route": "/tax", "aliases": ["harvest", "performance"]},
    {
        "label": "Tax — Harvest Plan",
        "route": "/tax/harvest/plan",
        "aliases": ["plan", "harvest", "tlh"],
    },
    {
        "label": "Tax — Projection",
        "route": "/tax/projection-config",
        "aliases": ["projection", "estimate"],
    },
    {"label": "Imports", "route": "/imports", "aliases": ["upload", "csv"]},
    {
        "label": "Verify",
        "route": "/verify",
        "aliases": ["verification", "audit", "reconciliation"],
    },
    {
        "label": "Wash Sales",
        "route": "/wash-sales",
        "aliases": ["1091", "violations"],
    },
    {"label": "Settings", "route": "/settings", "aliases": ["preferences"]},
    {
        "label": "Accounts",
        "route": "/settings/accounts",
        "aliases": ["account-types", "ira", "taxable"],
    },
    {
        "label": "Backups",
        "route": "/backup",
        "aliases": ["backup", "restore", "snapshot"],
    },
    {"label": "Carryforward", "route": "/settings/carryforward", "aliases": ["loss-carry"]},
    {"label": "Service", "route": "/settings/service", "aliases": ["launchd", "background"]},
]


# Cap on how many verify findings get embedded into the palette index. The
# bootstrap blob is parsed on every page render; we want the palette
# responsive on a noisy week without ballooning page size.
MAX_FINDINGS = 20


class _PaletteIndex(TypedDict):
    pages: list[_PageEntry]
    tickers: list[_TickerEntry]
    actions: list[_ActionEntry]
    findings: list[_FindingEntry]


def build_palette_index(repo: _PaletteRepo) -> _PaletteIndex:
    """Build the JSON-serializable palette index.

    Tier preference: held > targeted > traded. One ticker maps to exactly
    one tier. Tickers are sorted alphabetically; the client-side matcher
    re-sorts by score × tier multiplier.

    Sim verb actions are emitted only for symbols the user currently
    holds (qty > 0): "Sim sell SYM" and "Sim buy SYM". For a symbol the
    user no longer holds, navigating to /ticker/SYM via the ticker row
    is the right path.

    Verify findings are pulled from the most recent run, capped at
    ``MAX_FINDINGS`` so a noisy week doesn't bloat every page render.
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

    # Verb actions for held symbols only. We deliberately don't emit "buy"
    # actions for tickers we don't hold — that flow starts on /sim with the
    # symbol typed in, not via the palette.
    actions: list[_ActionEntry] = []
    for sym in sorted(held):
        actions.append(
            {
                "label": f"Sim sell {sym}",
                "route": f"/sim?ticker={sym}&action=sell",
                "verb": "sell",
                "sym": sym,
            }
        )
        actions.append(
            {
                "label": f"Sim buy {sym}",
                "route": f"/sim?ticker={sym}&action=buy",
                "verb": "buy",
                "sym": sym,
            }
        )

    findings: list[_FindingEntry] = []
    try:
        latest = repo.latest_verify_run()
    except Exception:  # noqa: BLE001 — palette must never break a page render
        latest = None
    if latest is not None:
        try:
            rows = repo.list_verify_findings(run_id=latest.id)
        except Exception:  # noqa: BLE001
            rows = []
        for f in rows[:MAX_FINDINGS]:
            findings.append(
                {
                    "label": f"{f.rule_id} — {f.scope}",
                    "route": "/verify",
                    "rule_id": str(f.rule_id),
                    "scope": str(f.scope),
                    "severity": str(f.severity),
                }
            )

    return {
        "pages": PAGES,
        "tickers": tickers,
        "actions": actions,
        "findings": findings,
    }
