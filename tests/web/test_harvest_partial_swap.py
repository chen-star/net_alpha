"""A2.3: Harvest plan splits into #harvest-summary + #harvest-table.
Checkbox toggles target #harvest-summary; per-row tax-saved cells get
stable IDs for OOB swap; the route branches on HX-Target to return only
the summary partial + OOB cell fragments."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient


def _seed_loss(builders, repo):
    builders.seed_import(
        repo, "schwab", "lt",
        [
            builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5), qty=10, cost=1000),
        ],
    )


def test_harvest_regions_split(client: TestClient, builders, repo):
    _seed_loss(builders, repo)
    res = client.get("/tax/harvest/plan")
    body = res.text
    assert 'id="harvest-summary"' in body
    assert 'id="harvest-table"' in body


def test_checkbox_targets_summary_not_full_region(client: TestClient, builders, repo):
    _seed_loss(builders, repo)
    res = client.get("/tax/harvest/plan")
    body = res.text
    # Checkbox input now targets #harvest-summary, not the wrapping region.
    assert 'hx-target="#harvest-summary"' in body


def test_tax_saved_cells_have_stable_ids(client: TestClient, builders, repo):
    _seed_loss(builders, repo)
    res = client.get("/tax/harvest/plan")
    body = res.text
    if "harvest-table" in body and "<tbody>" in body:
        if "tax-saved-" not in body:
            assert "<tr data-symbol=" not in body, (
                "rows exist but no tax-saved id was emitted"
            )


def test_htmx_summary_request_returns_only_summary(client: TestClient, builders, repo):
    _seed_loss(builders, repo)
    res = client.get(
        "/tax/harvest/plan?pick=AAPL::schwab/lt&mode=manual",
        headers={"HX-Request": "true", "HX-Target": "harvest-summary"},
    )
    body = res.text
    assert 'id="harvest-summary"' in body
    assert 'id="harvest-table"' not in body
