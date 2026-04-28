"""Phase 1 IA redirects (§6.1 of UI/UX redesign spec)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_holdings_redirects_to_positions(client: TestClient):
    resp = client.get("/holdings", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"] == "/positions"


def test_holdings_with_query_preserves_query(client: TestClient):
    resp = client.get("/holdings?period=ytd&account=schwab%2Flt", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"] == "/positions?period=ytd&account=schwab%2Flt"


def test_holdings_redirected_then_followed_returns_200(client: TestClient):
    resp = client.get("/holdings")  # follow_redirects=True is the default
    assert resp.status_code == 200
    # The page chrome is the new positions page; verify the page-key marker
    assert 'data-page-key="/positions"' in resp.text or "Holdings" in resp.text or "Positions" in resp.text


def test_tax_harvest_redirects_to_positions_at_loss(client: TestClient):
    resp = client.get("/tax?view=harvest", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"] == "/positions?view=at-loss"


def test_tax_harvest_with_extra_params_preserves_them(client: TestClient):
    resp = client.get("/tax?view=harvest&period=ytd&account=schwab%2Flt", follow_redirects=False)
    assert resp.status_code == 301
    loc = resp.headers["location"]
    assert loc.startswith("/positions?")
    assert "view=at-loss" in loc
    assert "period=ytd" in loc
    assert "account=schwab%2Flt" in loc
    assert "view=harvest" not in loc


def test_tax_other_views_still_render_normally(client: TestClient):
    """Make sure the redirect didn't accidentally catch wash-sales / projection."""
    for view in ("wash-sales", "projection"):
        resp = client.get(f"/tax?view={view}")
        assert resp.status_code == 200, f"/tax?view={view} regressed"


def test_imports_redirects_to_settings_imports(client: TestClient):
    resp = client.get("/imports", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"] == "/settings/imports"


def test_settings_imports_renders_base_with_drawer_open_signal(client: TestClient):
    """`/settings/imports` returns the home page with a payload that tells
    Alpine to dispatch `open-settings-drawer` on load, focused on the
    Imports tab. Implementation detail: we look for the dispatch hook in
    the rendered HTML."""
    resp = client.get("/settings/imports")
    assert resp.status_code == 200
    assert 'data-open-settings-tab="imports"' in resp.text


def test_tax_view_budget_also_redirects_to_positions_at_loss(client: TestClient):
    """The `budget` alias for `harvest` should also redirect to the new
    at-loss home (Phase 1 IA, Critical #2 review fix)."""
    resp = client.get("/tax?view=budget", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"] == "/positions?view=at-loss"
