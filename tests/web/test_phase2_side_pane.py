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
