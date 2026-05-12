"""A2.1: Tab links carry a `data-view-tab` attribute the JS reads on click,
and the tabs container has a `data-positions-tabs-root` marker so the script
attaches only there."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient


def test_tabs_root_marker_present(client: TestClient, builders, repo):
    builders.seed_import(
        repo, "schwab", "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/positions?view=stocks")
    assert res.status_code == 200
    assert 'data-positions-tabs-root' in res.text


def test_tab_links_have_view_attribute(client: TestClient, builders, repo):
    builders.seed_import(
        repo, "schwab", "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/positions?view=stocks")
    body = res.text
    assert 'data-view-tab="all"' in body
    assert 'data-view-tab="stocks"' in body
    assert 'data-view-tab="at-loss"' in body


def test_positions_tabs_script_registered(client: TestClient):
    res = client.get("/")
    assert res.status_code == 200
    assert 'positions_tabs.js' in res.text
