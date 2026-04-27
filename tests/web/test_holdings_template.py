"""Holdings table layout: no Realized column, Unrealized shows $ + %."""

from datetime import date

from fastapi.testclient import TestClient


def test_holdings_table_omits_realized_column(client: TestClient, builders, repo):
    builders.seed_import(repo, "schwab", "lt", [
        builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5), qty=10, cost=1500),
    ])
    res = client.get("/portfolio/positions?period=ytd&account=&group_options=merge&show=open&page=1")
    assert res.status_code == 200
    # Header text "YTD 2026 Realized" must not appear.
    assert "YTD 2026 Realized" not in res.text
    # And the column header tooltip text from the spec is gone:
    assert "Sum of (proceeds − cost basis)" not in res.text


def test_holdings_unrealized_shows_dollars_and_percent(client: TestClient, builders, repo, monkeypatch):
    """When a quote is available, Unrealized shows $ on top and % below."""
    from decimal import Decimal
    from datetime import datetime, timezone
    from net_alpha.pricing.provider import Quote
    from net_alpha.engine.stitch import stitch_account
    from net_alpha.engine.recompute import recompute_all_violations

    account, _ = builders.seed_import(repo, "schwab", "lt", [
        builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5), qty=10, cost=1000),
    ])

    # Stitch and run wash sale engine to create lots from the buy trades.
    stitch_account(repo, account.id)
    recompute_all_violations(repo, {})

    def fake_get_prices(self, symbols):
        return {"AAPL": Quote(
            symbol="AAPL",
            price=Decimal("150"),  # MV = 1500, unrealized = +500, +50%
            as_of=datetime.now(timezone.utc),
            source="yahoo",
        )}

    monkeypatch.setattr("net_alpha.pricing.service.PricingService.get_prices", fake_get_prices)

    res = client.get("/portfolio/positions?period=ytd&account=&group_options=merge&show=open&page=1")
    assert res.status_code == 200
    # Both dollar and percent should appear in the rendered cell.
    assert "+$500.00" in res.text
    assert "+50.0%" in res.text
