"""A5: HTMX-driven forms/buttons have hx-indicator pointing to a spinner."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient


def test_sim_submit_has_indicator(client: TestClient):
    res = client.get("/sim")
    body = res.text
    assert "spinner-inline" in body
    assert "hx-indicator" in body


def test_account_multi_select_has_spinner(client: TestClient, builders, repo):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/positions")
    body = res.text
    assert "spinner-inline" in body
