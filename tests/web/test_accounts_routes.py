"""Tests for /settings/accounts."""

from fastapi.testclient import TestClient


def test_settings_accounts_get_renders(client: TestClient):
    r = client.get("/settings/accounts")
    assert r.status_code == 200
    assert "Account types" in r.text


def test_settings_accounts_get_direct_navigation_renders_base_html_shell(client: TestClient):
    """Direct browser navigation (non-HTMX) must wrap the accounts fragment
    in base.html so the user gets the nav bar, dark theme, and footer —
    not an unstyled white page with browser-default fonts.

    Regression: the route used to always return the bare HTMX fragment,
    which looked completely broken when reached via URL bar or palette.
    """
    r = client.get("/settings/accounts")
    body = r.text
    assert "Account types" in body
    # base.html ships these markers; their absence means the route returned
    # a fragment instead of a full page.
    assert "<html" in body.lower()
    assert "<body" in body.lower()
    # Nav strip is part of the base shell.
    assert "net-alpha" in body


def test_settings_accounts_get_htmx_returns_bare_fragment(client: TestClient):
    """HTMX-driven swap-in must still receive just the fragment (no base.html
    wrapper), otherwise the swap target would double-nest <html>/<body>."""
    r = client.get("/settings/accounts", headers={"HX-Request": "true"})
    body = r.text
    assert "Account types" in body
    assert "<html" not in body.lower()
    assert "<body" not in body.lower()


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
