"""HTTP-level multi-account filter behavior on the Tax page."""
from __future__ import annotations
from fastapi.testclient import TestClient


def test_tax_no_account_param_shows_all_accounts(client: TestClient):
    resp = client.get("/tax")
    assert resp.status_code == 200
    assert "All accounts" in resp.text


def test_tax_legacy_single_account_param_works(client: TestClient):
    resp = client.get("/tax?account=Schwab%2FTax")
    assert resp.status_code == 200


def test_tax_repeated_account_query_returns_200(client: TestClient):
    resp = client.get("/tax",
                      params=[("account", "Schwab/Tax"), ("account", "Schwab/IRA")])
    assert resp.status_code == 200


def test_tax_empty_account_param_treated_as_all(client: TestClient):
    resp = client.get("/tax?account=")
    assert resp.status_code == 200


def test_tax_wash_sales_toolbar_renders_macro(client_with_data: TestClient):
    """Requires client_with_data so has_any_tax_data is true and the tab body renders."""
    resp = client_with_data.get("/tax?view=wash-sales")
    assert resp.status_code == 200
    assert 'data-testid="account-multi-select"' in resp.text


def test_harvest_plan_repeated_account_query_returns_200(client: TestClient):
    resp = client.get("/tax/harvest/plan",
                      params=[("account", "Schwab/Tax"), ("account", "Schwab/IRA")])
    assert resp.status_code == 200
