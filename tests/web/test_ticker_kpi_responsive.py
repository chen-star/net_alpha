"""B3: Ticker KPI grid uses a responsive cols-2/3/5 layout, and the
secondary KPIs sit inside a <details> with data-testid='ticker-kpi-more'."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient


def test_ticker_kpi_grid_is_responsive(client: TestClient, builders, repo):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/ticker/AAPL")
    body = res.text
    # Responsive grid class string is present.
    assert "grid-cols-2 md:grid-cols-3 xl:grid-cols-5" in body


def test_ticker_secondary_kpis_in_details(client: TestClient, builders, repo):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/ticker/AAPL")
    body = res.text
    assert 'data-testid="ticker-kpi-more"' in body
