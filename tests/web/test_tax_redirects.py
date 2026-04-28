"""Tests for /wash-sales -> /tax 301 redirect (Task 28)."""

from __future__ import annotations


def test_wash_sales_redirects_to_tax(client):
    resp = client.get("/wash-sales", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"].startswith("/tax")


def test_wash_sales_preserves_query_string(client):
    resp = client.get("/wash-sales?account=Schwab%20Tax&year=2025", follow_redirects=False)
    assert resp.status_code == 301
    loc = resp.headers["location"]
    assert "view=wash-sales" in loc
    assert "Schwab" in loc
    assert "year=2025" in loc


def test_wash_sales_calendar_redirects_with_view_normalised(client):
    # ?view=calendar is a sub-view that gets normalised to view=wash-sales by the redirect.
    resp = client.get("/wash-sales?view=calendar", follow_redirects=False)
    assert resp.status_code == 301
    assert "/tax" in resp.headers["location"]
    assert "view=wash-sales" in resp.headers["location"]
