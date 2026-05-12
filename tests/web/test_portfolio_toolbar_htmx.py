"""A2.2: Portfolio toolbar uses HTMX (not full reload) for period/account changes.
The subline element has a stable id for OOB updates; the /portfolio/body
endpoint emits the OOB subline fragment when called via HTMX."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient


def test_toolbar_form_has_hx_get(client: TestClient, builders, repo):
    builders.seed_import(
        repo, "schwab", "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/")
    assert res.status_code == 200
    body = res.text
    # HTMX attributes on the form
    assert 'hx-get="/portfolio/body"' in body
    assert 'hx-target="#portfolio-body"' in body
    assert 'hx-push-url="true"' in body
    # No more inline full-reload trigger on the period select
    assert 'onchange="this.form.submit()"' not in body


def test_subline_has_stable_id(client: TestClient, builders, repo):
    builders.seed_import(
        repo, "schwab", "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="portfolio-subline"' in res.text


def test_account_select_uses_request_submit(client: TestClient):
    res = client.get("/")
    assert res.status_code == 200
    body = res.text
    # The Alpine helper must call requestSubmit() so HTMX intercepts.
    assert "requestSubmit()" in body


def test_portfolio_body_emits_oob_subline_when_htmx(client: TestClient, builders, repo):
    builders.seed_import(
        repo, "schwab", "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get(
        "/portfolio/body?period=lifetime",
        headers={"HX-Request": "true", "HX-Target": "portfolio-body"},
    )
    assert res.status_code == 200
    body = res.text
    assert 'id="portfolio-subline"' in body
    assert 'hx-swap-oob="true"' in body
    assert "LIFETIME" in body.upper()
