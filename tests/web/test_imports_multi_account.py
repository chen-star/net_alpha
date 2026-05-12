"""Multi-account filter on the Imports page (new in Task 12)."""
from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient


def test_imports_no_account_param_shows_all(client: TestClient):
    """No filter → 'All accounts' label, all imports visible."""
    resp = client.get("/imports/_legacy_page")
    assert resp.status_code == 200
    assert "All accounts" in resp.text


def test_imports_repeated_account_query_returns_200(client: TestClient):
    resp = client.get(
        "/imports/_legacy_page",
        params=[("account", "Schwab/Tax"), ("account", "Schwab/IRA")],
    )
    assert resp.status_code == 200


def test_imports_legacy_single_account_works(client: TestClient):
    resp = client.get("/imports/_legacy_page?account=Schwab%2FTax")
    assert resp.status_code == 200


def test_imports_empty_account_param_treated_as_all(client: TestClient):
    resp = client.get("/imports/_legacy_page?account=")
    assert resp.status_code == 200
    assert "All accounts" in resp.text


def test_imports_toolbar_renders_account_multi_select_macro(client: TestClient):
    resp = client.get("/imports/_legacy_page")
    assert resp.status_code == 200
    assert 'data-testid="account-multi-select"' in resp.text


def test_imports_filtered_to_one_account_excludes_others(
    client: TestClient, repo
):
    """When two accounts exist, filtering to one excludes the other account's table row."""
    from tests.web.conftest import make_buy, seed_import

    day = date(2024, 3, 1)
    seed_import(
        repo, "schwab", "Personal",
        [make_buy("schwab/Personal", "AAPL", day)],
        csv_filename="personal.csv",
    )
    seed_import(
        repo, "schwab", "IRA",
        [make_buy("schwab/IRA", "MSFT", day)],
        csv_filename="ira.csv",
    )

    # Unfiltered: both CSV filenames appear.
    all_resp = client.get("/imports/_legacy_page")
    assert all_resp.status_code == 200
    assert "personal.csv" in all_resp.text
    assert "ira.csv" in all_resp.text

    # Filtered to schwab/Personal only: IRA's unique filename must not appear in
    # the table rows (only schwab/Personal's import record is in `imports`).
    filtered = client.get("/imports/_legacy_page?account=schwab%2FPersonal")
    assert filtered.status_code == 200
    assert "personal.csv" in filtered.text
    assert "ira.csv" not in filtered.text
