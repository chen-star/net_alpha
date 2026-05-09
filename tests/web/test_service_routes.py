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


def test_status_pill_endpoint_renders_a_state_class(client):
    r = client.get("/settings/service/pill")
    assert r.status_code == 200
    # Always renders one of the four state classes
    assert any(s in r.text for s in ["pill--running", "pill--paused", "pill--stale", "pill--stopped", "pill--unknown"])


def test_post_control_pause_returns_200_and_a_pill(client):
    r = client.post("/settings/service/control", data={"action": "pause"})
    assert r.status_code == 200
    # The control endpoint returns the freshly-rendered pill, so it should contain a CSS class.
    assert "status-pill" in r.text or "pill--" in r.text
