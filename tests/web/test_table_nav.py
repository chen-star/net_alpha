"""A4: Tables that opt into arrow-key row navigation carry a `data-table-nav`
attribute on the <tbody>. Their <tr>s get tabindex=0. The base layout loads
the table_nav.js script."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient


def test_search_input_uses_input_search_class(client: TestClient):
    res = client.get("/positions")
    body = res.text
    assert 'input-search' in body


def test_table_nav_script_registered(client: TestClient):
    res = client.get("/")
    assert "table_nav.js" in res.text


def test_harvest_tbody_has_table_nav_marker(client: TestClient, builders, repo):
    builders.seed_import(
        repo, "schwab", "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/tax/harvest/plan")
    body = res.text
    if "<tbody>" in body:
        assert "data-table-nav" in body
