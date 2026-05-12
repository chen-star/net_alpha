"""A5: HTMX-driven forms/buttons have hx-indicator pointing to a spinner."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient


def test_sim_submit_has_indicator(client: TestClient):
    res = client.get("/sim")
    body = res.text
    assert "spinner-inline" in body
    assert "hx-indicator" in body


def test_portfolio_toolbar_has_spinner(client: TestClient, builders, repo):
    """The Portfolio toolbar runs in HTMX mode (toolbar_hx_target is set on
    that route only), so its form gets an hx-indicator + spinner. Other
    pages render the same toolbar macro in plain-GET mode and intentionally
    don't carry the spinner — there's no HTMX request to indicate."""
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/")
    body = res.text
    assert 'id="portfolio-toolbar-spinner"' in body
    assert "spinner-inline" in body
