"""Tests for /settings/service routes."""

from fastapi.testclient import TestClient


def test_settings_service_renders_status(client: TestClient):
    r = client.get("/settings/service")
    assert r.status_code == 200
    assert "Service status" in r.text
    assert "Schedules" in r.text


def test_settings_service_runs_fragment(client: TestClient):
    r = client.get("/settings/service/runs", headers={"hx-request": "true"})
    assert r.status_code == 200
