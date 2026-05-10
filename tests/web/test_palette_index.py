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
    ) -> None:
        self._all = list(all_tickers)
        self._held = set(held_tickers)
        self._targets = set(target_tickers)

    def list_distinct_tickers(self) -> list[str]:
        return sorted(self._all)

    def tickers_with_open_lots(self) -> set[str]:
        return set(self._held)

    def distinct_target_tickers(self) -> list[str]:
        return sorted(self._targets)


def test_pages_constant_is_nonempty_and_each_has_route():
    assert PAGES, "PAGES must declare at least one navigation entry"
    for page in PAGES:
        assert page["label"]
        assert page["route"].startswith("/")


def test_index_includes_declared_pages_verbatim():
    repo = _StubRepo(all_tickers=[], held_tickers=[], target_tickers=[])
    index = build_palette_index(repo)
    assert index["pages"] == PAGES


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
