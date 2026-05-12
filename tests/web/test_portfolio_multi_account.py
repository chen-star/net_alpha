"""HTTP-level multi-account filter behavior on the Portfolio page."""
from __future__ import annotations
from fastapi.testclient import TestClient


def test_portfolio_no_account_param_shows_all_accounts(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "All accounts" in resp.text


def test_portfolio_legacy_single_account_param_still_works(client: TestClient):
    """Backwards-compat: `?account=X` from old bookmarks still parses to a 1-element list."""
    # Seed nothing — just confirm the route accepts the param and returns 200.
    resp = client.get("/?account=Schwab%2FTax")
    assert resp.status_code == 200


def test_portfolio_repeated_account_query_returns_200(client: TestClient):
    """Multi: ?account=A&account=B must be accepted by FastAPI."""
    resp = client.get("/", params=[("account", "Schwab/Tax"), ("account", "Schwab/IRA")])
    assert resp.status_code == 200


def test_portfolio_empty_account_param_treated_as_all(client: TestClient):
    """Compat with the old <select value=''>All accounts</select> form behavior."""
    resp = client.get("/?account=")
    assert resp.status_code == 200
    assert "All accounts" in resp.text


def test_portfolio_toolbar_renders_account_multi_select_macro(client_with_data: TestClient):
    """The toolbar's Account control is the new checkbox dropdown, not <select>.

    Requires `client_with_data` so `imports` is non-empty and the toolbar is rendered.
    """
    resp = client_with_data.get("/")
    assert resp.status_code == 200
    # The macro has data-testid="account-multi-select"; the old <select name="account"> is gone.
    assert 'data-testid="account-multi-select"' in resp.text
    # Old single-<select> sentinel removed:
    assert '<select name="account"' not in resp.text
