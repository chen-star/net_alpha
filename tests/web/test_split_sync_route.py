"""POST /splits/sync triggers PricingService.sync_splits and returns counts."""

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_post_splits_sync_with_all_returns_summary(client: TestClient, builders, repo):
    builders.seed_import(repo, "schwab", "lt", [
        builders.make_buy("schwab/lt", "AAPL", date(2020, 1, 5), qty=10, cost=1500),
    ])
    from net_alpha.engine.etf_pairs import load_etf_pairs
    from net_alpha.engine.recompute import recompute_all_violations
    recompute_all_violations(repo, load_etf_pairs())

    # Stub the provider's fetch_splits to return one event for AAPL.
    from net_alpha.pricing.provider import SplitEvent
    def fake_fetch(self, symbol):
        if symbol == "AAPL":
            return [SplitEvent(symbol="AAPL", split_date=date(2020, 8, 31), ratio=2.0)]
        return []
    with patch("net_alpha.pricing.yahoo.YahooPriceProvider.fetch_splits", fake_fetch):
        res = client.post("/splits/sync?symbols=ALL")

    assert res.status_code == 200
    body = res.json()
    assert body["applied_count"] == 1
    assert body["skipped_count"] == 0
    assert body["error_symbols"] == []


def test_post_splits_sync_with_specific_symbol(client: TestClient, builders, repo):
    builders.seed_import(repo, "schwab", "lt", [
        builders.make_buy("schwab/lt", "NVDA", date(2020, 1, 5), qty=10, cost=2000),
    ])
    from net_alpha.engine.etf_pairs import load_etf_pairs
    from net_alpha.engine.recompute import recompute_all_violations
    recompute_all_violations(repo, load_etf_pairs())

    with patch("net_alpha.pricing.yahoo.YahooPriceProvider.fetch_splits", return_value=[]):
        res = client.post("/splits/sync?symbols=NVDA")

    assert res.status_code == 200
