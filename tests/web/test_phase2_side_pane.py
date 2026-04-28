"""Phase 2 side pane (§3.5, §6.2 NEW)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_positions_page_mounts_side_pane_skeleton(client: TestClient):
    resp = client.get("/positions")
    assert resp.status_code == 200
    html = resp.text
    assert 'id="positions-pane"' in html
    assert 'data-testid="positions-pane-close"' in html


def test_positions_pane_listens_for_open_event(client: TestClient):
    resp = client.get("/positions")
    html = resp.text
    assert "open-positions-pane" in html


def test_positions_pane_endpoint_returns_fragment(client: TestClient):
    """`/positions/pane?sym=NVDA` returns a partial without the page chrome."""
    resp = client.get("/positions/pane?sym=NVDA")
    assert resp.status_code == 200
    html = resp.text
    assert "<html" not in html.lower()
    assert "NVDA" in html


def test_positions_pane_endpoint_404s_on_missing_sym(client: TestClient):
    resp = client.get("/positions/pane")
    assert resp.status_code in (400, 422)
