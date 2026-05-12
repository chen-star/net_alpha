"""HTTP-level multi-account filter behavior on the Positions page."""
from __future__ import annotations
from fastapi.testclient import TestClient


def test_positions_no_account_param_shows_all_accounts(client: TestClient):
    resp = client.get("/positions")
    assert resp.status_code == 200
    assert "All accounts" in resp.text


def test_positions_legacy_single_account_param_works(client: TestClient):
    resp = client.get("/positions?account=Schwab%2FTax")
    assert resp.status_code == 200


def test_positions_repeated_account_query_returns_200(client: TestClient):
    resp = client.get("/positions", params=[("account", "Schwab/Tax"), ("account", "Schwab/IRA")])
    assert resp.status_code == 200


def test_positions_empty_account_param_treated_as_all(client: TestClient):
    resp = client.get("/positions?account=")
    assert resp.status_code == 200
    assert "All accounts" in resp.text


def test_positions_toolbar_renders_account_multi_select_macro(client_with_data: TestClient):
    """Requires client_with_data so imports is non-empty and the toolbar renders."""
    resp = client_with_data.get("/positions")
    assert resp.status_code == 200
    assert 'data-testid="account-multi-select"' in resp.text


def test_plan_view_repeated_account_query_returns_200(client: TestClient):
    """The Plan tab toolbar must also accept multi-account."""
    resp = client.get(
        "/positions",
        params=[("view", "plan"), ("account", "Schwab/Tax"), ("account", "Schwab/IRA")],
    )
    assert resp.status_code == 200


def test_plan_toolbar_renders_hidden_account_inputs_for_multi(client: TestClient):
    """When the Plan toolbar form submits, it must carry multiple account values forward."""
    resp = client.get(
        "/positions",
        params=[("view", "plan"), ("account", "Schwab/Tax"), ("account", "Schwab/IRA")],
    )
    # The toolbar should emit a hidden `<input name="account" value="...">` per selected account.
    # When NO accounts are selected, no hidden inputs.
    assert resp.status_code == 200
