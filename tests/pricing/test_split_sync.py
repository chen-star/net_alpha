"""PricingService.sync_splits orchestrates fetch + persist + apply."""

from dataclasses import dataclass
from datetime import date

from net_alpha.pricing.provider import SplitEvent
from net_alpha.pricing.service import PricingService


@dataclass
class _StubProvider:
    events_by_symbol: dict[str, list[SplitEvent]]

    def get_quotes(self, symbols):
        return {}

    def fetch_splits(self, symbol):
        return self.events_by_symbol.get(symbol, [])


def test_sync_splits_inserts_new_splits_and_applies_them(repo, builders, tmp_path):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [
            builders.make_buy("schwab/lt", "AAPL", date(2020, 1, 5), qty=10, cost=1500),
        ],
    )
    from net_alpha.engine.etf_pairs import load_etf_pairs
    from net_alpha.engine.recompute import recompute_all_violations

    recompute_all_violations(repo, load_etf_pairs())

    provider = _StubProvider({"AAPL": [SplitEvent(symbol="AAPL", split_date=date(2020, 8, 31), ratio=2.0)]})
    from net_alpha.pricing.cache import PriceCache

    cache = PriceCache(repo.engine, ttl_seconds=300)
    svc = PricingService(provider=provider, cache=cache, enabled=True)

    result = svc.sync_splits(["AAPL"], repo=repo)

    assert result.applied_count == 1
    assert result.skipped_count == 0
    assert result.error_symbols == []

    lots = repo.get_lots_for_ticker("AAPL")
    assert lots[0].quantity == 20.0


def test_sync_splits_returns_skipped_for_already_known(repo, builders):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [
            builders.make_buy("schwab/lt", "AAPL", date(2020, 1, 5), qty=10, cost=1500),
        ],
    )
    from net_alpha.engine.etf_pairs import load_etf_pairs
    from net_alpha.engine.recompute import recompute_all_violations

    recompute_all_violations(repo, load_etf_pairs())
    repo.add_split("AAPL", date(2020, 8, 31), 2.0, "yahoo")  # pre-existing

    provider = _StubProvider({"AAPL": [SplitEvent(symbol="AAPL", split_date=date(2020, 8, 31), ratio=2.0)]})
    from net_alpha.pricing.cache import PriceCache

    cache = PriceCache(repo.engine, ttl_seconds=300)
    svc = PricingService(provider=provider, cache=cache, enabled=True)

    result = svc.sync_splits(["AAPL"], repo=repo)
    assert result.skipped_count == 1


def test_sync_splits_disabled_returns_immediately(repo):
    from net_alpha.pricing.cache import PriceCache

    cache = PriceCache(repo.engine, ttl_seconds=300)
    svc = PricingService(
        provider=_StubProvider({"AAPL": [SplitEvent(symbol="AAPL", split_date=date(2020, 8, 31), ratio=2.0)]}),
        cache=cache,
        enabled=False,
    )

    result = svc.sync_splits(["AAPL"], repo=repo)

    assert result.applied_count == 0
    assert result.skipped_count == 0
    assert "AAPL" in result.error_symbols  # treated as unable-to-fetch
