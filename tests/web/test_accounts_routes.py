"""Tests for /settings/accounts."""

from fastapi.testclient import TestClient


def test_settings_accounts_get_renders(client: TestClient):
    r = client.get("/settings/accounts")
    assert r.status_code == 200
    assert "Account types" in r.text


def test_settings_accounts_post_invalid_type_returns_400(client: TestClient):
    r = client.post(
        "/settings/accounts",
        data={
            "broker": "schwab",
            "label": "test",
            "type": "garbage_type",
        },
    )
    assert r.status_code == 400
