"""Tests for build_palette_index — the pure server-side builder for the ⌘K
palette JSON bootstrap. Tier ranking: held > targeted > traded; one ticker
maps to exactly one tier.
"""

from __future__ import annotations

from net_alpha.web.palette import PAGES, build_palette_index


class _StubRepo:
    """Minimal Repository-shaped stub for unit tests."""

    def __init__(
        self,
        *,
        all_tickers: list[str],
        held_tickers: list[str],
        target_tickers: list[str],
        latest_run: object | None = None,
        findings: list | None = None,
    ) -> None:
        self._all = list(all_tickers)
        self._held = set(held_tickers)
        self._targets = set(target_tickers)
        self._latest_run = latest_run
        self._findings = findings or []

    def list_distinct_tickers(self) -> list[str]:
        return sorted(self._all)

    def tickers_with_open_lots(self) -> set[str]:
        return set(self._held)

    def distinct_target_tickers(self) -> list[str]:
        return sorted(self._targets)

    def latest_verify_run(self):
        return self._latest_run

    def list_verify_findings(self, *, run_id: int) -> list:
        return list(self._findings)


class _Run:
    def __init__(self, id: int) -> None:
        self.id = id


class _Finding:
    def __init__(self, rule_id: str, scope: str, severity: str = "warn") -> None:
        self.rule_id = rule_id
        self.scope = scope
        self.severity = severity


def test_pages_constant_is_nonempty_and_each_has_route():
    assert PAGES, "PAGES must declare at least one navigation entry"
    for page in PAGES:
        assert page["label"]
        assert page["route"].startswith("/")


def test_index_includes_declared_pages_verbatim():
    repo = _StubRepo(all_tickers=[], held_tickers=[], target_tickers=[])
    index = build_palette_index(repo)
    assert index["pages"] == PAGES


def test_pages_include_verify_and_wash_sales_routes():
    """Regression: these were added when the palette grew to cover the
    expanded /verify and /wash-sales surfaces — make sure they don't
    silently drop out of PAGES."""
    routes = {p["route"] for p in PAGES}
    assert "/verify" in routes
    assert "/wash-sales" in routes
    assert "/tax/harvest/plan" in routes
    assert "/settings/accounts" in routes
    assert "/backup" in routes


def test_actions_emit_sim_verbs_for_held_tickers_only():
    """Sim sell/buy actions only fire for currently-held symbols. A
    targeted-but-not-held symbol should not produce action rows."""
    repo = _StubRepo(
        all_tickers=["AAPL", "NVDA"],
        held_tickers=["AAPL"],
        target_tickers=["NVDA"],
    )
    index = build_palette_index(repo)
    syms = sorted({a["sym"] for a in index["actions"]})
    assert syms == ["AAPL"]
    labels = sorted(a["label"] for a in index["actions"])
    assert labels == ["Sim buy AAPL", "Sim sell AAPL"]
    by_verb = {a["verb"]: a["route"] for a in index["actions"]}
    assert by_verb["sell"] == "/sim?ticker=AAPL&action=sell"
    assert by_verb["buy"] == "/sim?ticker=AAPL&action=buy"


def test_actions_empty_when_no_holdings():
    repo = _StubRepo(all_tickers=["AAPL"], held_tickers=[], target_tickers=[])
    index = build_palette_index(repo)
    assert index["actions"] == []


def test_findings_pulled_from_latest_verify_run():
    repo = _StubRepo(
        all_tickers=[],
        held_tickers=[],
        target_tickers=[],
        latest_run=_Run(id=7),
        findings=[
            _Finding("BasisRecon", "AAPL/Schwab-Taxable", "fail"),
            _Finding("OV-1", "global", "warn"),
        ],
    )
    index = build_palette_index(repo)
    labels = [f["label"] for f in index["findings"]]
    assert "BasisRecon — AAPL/Schwab-Taxable" in labels
    assert "OV-1 — global" in labels
    # Every finding routes to /verify; the rank step (client-side) handles
    # text-match search by rule_id and scope.
    assert {f["route"] for f in index["findings"]} == {"/verify"}


def test_findings_empty_when_no_run_yet():
    repo = _StubRepo(
        all_tickers=[],
        held_tickers=[],
        target_tickers=[],
        latest_run=None,
        findings=[],
    )
    index = build_palette_index(repo)
    assert index["findings"] == []


def test_findings_capped_so_palette_stays_small():
    """A noisy verify run with hundreds of findings must not bloat every
    page render. Cap is MAX_FINDINGS (20 as of this change)."""
    from net_alpha.web.palette import MAX_FINDINGS

    many = [_Finding(f"R-{i}", f"sym/{i}", "warn") for i in range(MAX_FINDINGS + 50)]
    repo = _StubRepo(
        all_tickers=[],
        held_tickers=[],
        target_tickers=[],
        latest_run=_Run(id=1),
        findings=many,
    )
    index = build_palette_index(repo)
    assert len(index["findings"]) == MAX_FINDINGS


def test_tier_held_ranks_above_targeted():
    repo = _StubRepo(
        all_tickers=["AAPL", "NVDA"],
        held_tickers=["AAPL"],
        target_tickers=["NVDA"],
    )
    index = build_palette_index(repo)
    by_sym = {row["sym"]: row["tier"] for row in index["tickers"]}
    assert by_sym["AAPL"] == "held"
    assert by_sym["NVDA"] == "targeted"


def test_held_and_targeted_both_resolves_to_held():
    """Tier preference: held wins when a ticker is both held and targeted."""
    repo = _StubRepo(
        all_tickers=["MSFT"],
        held_tickers=["MSFT"],
        target_tickers=["MSFT"],
    )
    index = build_palette_index(repo)
    assert index["tickers"] == [{"sym": "MSFT", "tier": "held"}]


def test_traded_only_falls_to_traded_tier():
    repo = _StubRepo(
        all_tickers=["OLD"],
        held_tickers=[],
        target_tickers=[],
    )
    index = build_palette_index(repo)
    assert index["tickers"] == [{"sym": "OLD", "tier": "traded"}]


def test_empty_db_yields_empty_ticker_list():
    repo = _StubRepo(all_tickers=[], held_tickers=[], target_tickers=[])
    index = build_palette_index(repo)
    assert index["tickers"] == []


def test_tickers_sorted_alphabetically_within_index():
    repo = _StubRepo(
        all_tickers=["TSLA", "AAPL", "NVDA"],
        held_tickers=[],
        target_tickers=[],
    )
    index = build_palette_index(repo)
    syms = [row["sym"] for row in index["tickers"]]
    assert syms == sorted(syms)
