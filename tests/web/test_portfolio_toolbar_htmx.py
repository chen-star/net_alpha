"""A2.2: Portfolio toolbar uses HTMX (not full reload) for period/account changes.
The subline element has a stable id for OOB updates; the /portfolio/body
endpoint emits the OOB subline fragment when called via HTMX."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient


def test_toolbar_form_has_hx_get(client: TestClient, builders, repo):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/")
    assert res.status_code == 200
    body = res.text
    # HTMX attributes on the form
    assert 'hx-get="/portfolio/body"' in body
    assert 'hx-target="#portfolio-body"' in body
    # hx-push-url is intentionally absent: HTMX would push the fragment URL
    # (/portfolio/body?…) into the address bar, which reload-breaks the page.
    # /portfolio/body now sets a canonical `/?…` URL via the HX-Push-Url
    # response header on HTMX requests instead.
    assert 'hx-push-url="true"' not in body
    # No more inline full-reload trigger on the period select
    assert 'onchange="this.form.submit()"' not in body


def test_subline_has_stable_id(client: TestClient, builders, repo):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="portfolio-subline"' in res.text


def test_account_select_uses_request_submit(client: TestClient, builders, repo):
    # The profile switcher's per-account <select> uses requestSubmit() — its
    # form has no explicit hx-trigger so HTMX's default 'submit' trigger
    # fires. (The account multi-select dropdown, by contrast, dispatches a
    # 'change' Event — see test_account_select_dispatches_change_not_submit.)
    # Seed an import so the profile switcher renders in the topbar.
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/")
    assert res.status_code == 200
    body = res.text
    assert "requestSubmit()" in body


def test_account_select_dispatches_change_not_submit(client: TestClient):
    """A2.2 bugfix: the multi-select Alpine helper must dispatch a 'change'
    event on the form (so HTMX's `change from:input[type=checkbox]`
    listener picks it up) — when the parent form has hx attrs. The helper
    now lives in /static/account_multi_select.js (extracted from the macro
    so window.accountMultiSelect is defined before Alpine's first init
    pass), so the substring check has moved with it."""
    page = client.get("/")
    assert page.status_code == 200
    # The page must reference the static helper so it loads before alpine.
    assert "/static/account_multi_select.js" in page.text

    js = client.get("/static/account_multi_select.js")
    assert js.status_code == 200
    body = js.text
    # New behavior: dispatch a change Event on the form when it's HTMX-driven.
    assert "new Event('change'" in body or 'new Event("change"' in body
    assert "form.dispatchEvent" in body or "dispatchEvent(new Event" in body


def test_positions_toolbar_is_plain_get_form(client: TestClient, builders, repo):
    """A2.2 fix: the shared toolbar only uses HTMX when the rendering route
    sets toolbar_hx_target. On Positions, the toolbar must fall back to a
    plain GET form (otherwise it tries to swap a #portfolio-body that
    doesn't exist on that page)."""
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/positions")
    assert res.status_code == 200
    body = res.text
    # The form's `action` attr is /positions (existing assertion in test_toolbar_action).
    assert 'action="/positions"' in body
    # But the HTMX swap attrs are NOT on the form on this page.
    # Scope to the toolbar form: look for the kpi-card flex form that doesn't
    # have hx-get="/portfolio/body".
    # A coarse but reliable check: hx-get="/portfolio/body" appears at most
    # zero times on the positions page.
    assert 'hx-get="/portfolio/body"' not in body
    # And the period select reverts to the inline submit handler.
    assert 'onchange="this.form.submit()"' in body


def test_portfolio_body_sets_canonical_hx_push_url(client: TestClient, builders, repo):
    """When the toolbar HTMX-swaps the body, the response must set
    HX-Push-Url to a canonical `/?…` URL, so reloads and shares land back
    on the full Overview page (not the body fragment endpoint)."""
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get(
        "/portfolio/body?period=lifetime&account=schwab/lt",
        headers={"HX-Request": "true", "HX-Target": "portfolio-body"},
    )
    assert res.status_code == 200
    push = res.headers.get("HX-Push-Url", "")
    assert push.startswith("/?")
    assert "period=lifetime" in push
    assert "account=schwab%2Flt" in push


def test_portfolio_body_no_hx_push_url_on_direct_get(client: TestClient, builders, repo):
    """Direct (non-HTMX) GETs do not set HX-Push-Url — only HTMX swaps need it."""
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/portfolio/body?period=ytd")
    assert res.status_code == 200
    assert "HX-Push-Url" not in res.headers


def test_portfolio_body_emits_oob_subline_when_htmx(client: TestClient, builders, repo):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
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
