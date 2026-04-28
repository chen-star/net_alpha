"""Phase 1 settings drawer tabs (§3.6 of UI/UX redesign spec)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_drawer_has_five_tab_buttons(client: TestClient):
    resp = client.get("/")
    html = resp.text
    for label in ("Imports", "Profile", "Density", "ETF pairs", "About"):
        assert f">{label}<" in html, f"missing tab: {label}"


def test_drawer_close_button_present(client: TestClient):
    resp = client.get("/")
    assert 'data-testid="settings-drawer-close"' in resp.text


def test_drawer_active_tab_starts_as_imports(client: TestClient):
    resp = client.get("/")
    html = resp.text
    imp_idx = html.find(">Imports<")
    assert imp_idx > 0
    btn_start = html.rfind("<button", 0, imp_idx)
    btn_html = html[btn_start:imp_idx]
    assert "data-tab=\"imports\"" in btn_html


def test_drawer_imports_tab_lazy_loads_from_legacy_endpoint(client: TestClient):
    """The drawer's Imports tab pulls content from /imports/_legacy_page
    via HTMX so the home page doesn't pay the imports DB cost on every load."""
    resp = client.get("/")
    assert 'hx-get="/imports/_legacy_page"' in resp.text
