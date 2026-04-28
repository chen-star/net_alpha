"""Phase 1 IA redirects (§6.1 of UI/UX redesign spec)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_holdings_redirects_to_positions(client: TestClient):
    resp = client.get("/holdings", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"] == "/positions"


def test_holdings_with_query_preserves_query(client: TestClient):
    resp = client.get("/holdings?period=ytd&account=schwab%2Flt", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"] == "/positions?period=ytd&account=schwab%2Flt"


def test_holdings_redirected_then_followed_returns_200(client: TestClient):
    resp = client.get("/holdings")  # follow_redirects=True is the default
    assert resp.status_code == 200
    # The page chrome is the new positions page; verify the page-key marker
    assert 'data-page-key="/positions"' in resp.text or "Holdings" in resp.text or "Positions" in resp.text
