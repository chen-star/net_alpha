"""Test install-offer rendering on the welcome page."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from net_alpha.service import control


def test_welcome_shows_install_offer_when_service_not_installed(client: TestClient):
    """When service is not installed (test default), the offer should appear."""
    from net_alpha.service.control import Status

    fake_status = Status(installed=False, running=False, paused=False, pid=None, disabled=False)
    with patch.object(control, "status", return_value=fake_status):
        r = client.get("/welcome")
    assert r.status_code == 200
    assert "Run net-alpha in the background" in r.text or "Install as service" in r.text


def test_welcome_hides_install_offer_when_service_installed(client: TestClient):
    """When the service is already installed, the offer should not appear."""
    from net_alpha.service.control import Status

    fake_status = Status(installed=True, running=True, paused=False, pid=12345, disabled=False)
    with patch.object(control, "status", return_value=fake_status):
        r = client.get("/welcome")
    assert r.status_code == 200
    assert "Install as service" not in r.text


def test_install_service_post_failure_returns_500(client: TestClient):
    """A failed install attempt returns a 500 with an error message."""
    with patch.object(control, "install", side_effect=RuntimeError("launchctl failed")):
        r = client.post("/welcome/install-service")
    assert r.status_code == 500
    assert "Install failed" in r.text


def test_install_service_post_success_redirects_to_root(client: TestClient):
    """A successful install redirects to /."""
    with patch.object(control, "install", return_value=None):
        r = client.post("/welcome/install-service", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert r.headers["location"] == "/"
