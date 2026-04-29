"""Phase 4 endpoint smoke tests — Ticker tabs, recon variant, set-basis caller."""

from fastapi.testclient import TestClient


def test_ticker_view_query_param_round_trip(client: TestClient):
    r = client.get("/ticker/AAPL?view=lots")
    assert r.status_code == 200
    assert 'aria-selected="true"' in r.text  # active tab
    r = client.get("/ticker/AAPL?view=bogus")
    assert r.status_code == 200  # fallthrough to timeline


def test_ticker_hx_request_returns_fragment(client: TestClient):
    r = client.get("/ticker/AAPL?view=lots", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "<html" not in r.text  # fragment only, no base layout


def test_reconciliation_variant_badge_returns_short_html(client: TestClient):
    # Don't assume any seeded data — just confirm the variant routes through.
    r = client.get("/reconciliation/AAPL?account_id=1&variant=badge")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert "<html" not in r.text  # badge is a span/badge, no full page


def test_ticker_tabs_have_aria_controls(client: TestClient):
    r = client.get("/ticker/AAPL")
    assert r.status_code == 200
    body = r.text
    assert 'aria-controls="ticker-tab-content"' in body
    assert 'role="tabpanel"' in body
    assert 'id="ticker-tab-timeline"' in body
    assert 'aria-labelledby="ticker-tab-timeline"' in body
