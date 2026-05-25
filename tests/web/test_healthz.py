from __future__ import annotations

from fastapi.testclient import TestClient


def test_healthz_ok(client: TestClient):
    """A booted app with a reachable DB reports healthy."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_healthz_is_not_gated_by_same_origin_guard(client: TestClient):
    """GET requests are never gated, so the healthcheck works without headers."""
    resp = client.get("/healthz", headers={"referer": "https://evil.example.com"})
    assert resp.status_code == 200
