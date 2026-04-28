"""Phase 1 gear icon (§3.6 / §5.13 of UI/UX redesign spec)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_gear_icon_present_in_topbar_on_every_page(client: TestClient):
    for path in ("/", "/positions", "/tax", "/sim"):
        resp = client.get(path)
        assert resp.status_code == 200
        assert 'data-testid="settings-gear"' in resp.text, f"missing gear on {path}"


def test_gear_icon_dispatches_open_settings_drawer_event(client: TestClient):
    resp = client.get("/")
    html = resp.text
    assert "open-settings-drawer" in html
    assert "$dispatch" in html or "@click" in html


def test_gear_icon_uses_lucide_settings_svg(client: TestClient):
    resp = client.get("/")
    assert "/static/icons/settings.svg" in resp.text
