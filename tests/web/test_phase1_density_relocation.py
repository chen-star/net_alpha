"""Phase 1 density toggle relocation (audit H4, T1)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_density_toggle_no_longer_in_positions_chrome(client: TestClient):
    """The /positions page no longer shows the density toggle inline.
    The toggle now lives in the Settings drawer's Density tab."""
    resp = client.get("/positions")
    html = resp.text
    drawer_start = html.find('id="settings-drawer-root"')
    body_html = html[:drawer_start] if drawer_start > 0 else html
    assert "Density:" not in body_html, "density toggle still present in positions chrome"


def test_density_toggle_no_longer_in_tax_chrome(client: TestClient):
    resp = client.get("/tax")
    html = resp.text
    drawer_start = html.find('id="settings-drawer-root"')
    body_html = html[:drawer_start] if drawer_start > 0 else html
    assert "Density:" not in body_html


def test_density_toggle_no_longer_in_imports_legacy_page_chrome(client: TestClient):
    """The legacy imports page (now reached via /imports/_legacy_page) drops
    its inline density toggle. The drawer hosts it."""
    resp = client.get("/imports/_legacy_page")
    html = resp.text
    drawer_start = html.find('id="settings-drawer-root"')
    body_html = html[:drawer_start] if drawer_start > 0 else html
    assert "Density:" not in body_html
