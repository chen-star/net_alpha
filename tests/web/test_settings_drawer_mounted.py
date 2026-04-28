"""Settings drawer skeleton must be mounted on every page (§3.6)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_settings_drawer_present_on_portfolio(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'id="settings-drawer"' in resp.text


def test_settings_drawer_present_on_holdings(client: TestClient):
    resp = client.get("/holdings")
    assert resp.status_code == 200
    assert 'id="settings-drawer"' in resp.text


def test_settings_drawer_present_on_tax(client: TestClient):
    resp = client.get("/tax")
    assert resp.status_code == 200
    assert 'id="settings-drawer"' in resp.text


def test_settings_drawer_present_on_imports(client: TestClient):
    resp = client.get("/imports")
    assert resp.status_code == 200
    assert 'id="settings-drawer"' in resp.text
