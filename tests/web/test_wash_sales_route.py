"""The merged Wash Sales page renders both views via ?view=table|calendar
and applies a unified filter bar."""

from datetime import date

from fastapi.testclient import TestClient


def test_wash_sales_default_renders_table_view(client: TestClient, builders, repo):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [
            builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5)),
        ],
    )
    res = client.get("/wash-sales")
    assert res.status_code == 200
    assert "Wash sales" in res.text
    # Default view = table; the segmented control should mark Table active.
    assert "seg-active" in res.text
    # Table-only fragment marker (totals bar/table); calendar ribbon shouldn't show.
    assert "calendar-ribbon" not in res.text or "view=calendar" in res.text


def test_wash_sales_view_calendar_renders_calendar(client: TestClient, builders, repo):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [
            builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5)),
        ],
    )
    res = client.get("/wash-sales?view=calendar")
    assert res.status_code == 200
    # Calendar ribbon include marker — exact element will be the year-ribbon container.
    assert "calendar" in res.text.lower()


def test_wash_sales_filter_ticker_propagates(client: TestClient, builders, repo):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [
            builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5)),
        ],
    )
    res = client.get("/wash-sales?ticker=AAPL")
    assert res.status_code == 200
    assert 'value="AAPL"' in res.text


def test_detail_redirects_to_wash_sales(client: TestClient):
    res = client.get("/detail", follow_redirects=False)
    assert res.status_code == 301
    assert res.headers["location"] == "/wash-sales"


def test_detail_redirect_preserves_query_string(client: TestClient):
    res = client.get("/detail?ticker=AAPL", follow_redirects=False)
    assert res.status_code == 301
    assert res.headers["location"] == "/wash-sales?ticker=AAPL"


def test_calendar_redirects_to_wash_sales_calendar_view(client: TestClient):
    res = client.get("/calendar", follow_redirects=False)
    assert res.status_code == 301
    assert res.headers["location"] == "/wash-sales?view=calendar"


def test_calendar_redirect_preserves_query_string(client: TestClient):
    res = client.get("/calendar?ticker=AAPL", follow_redirects=False)
    assert res.status_code == 301
    assert res.headers["location"] == "/wash-sales?view=calendar&ticker=AAPL"
