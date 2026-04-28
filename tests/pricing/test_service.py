import datetime as dt
from decimal import Decimal

from sqlmodel import create_engine

import net_alpha.db.tables as _tables  # noqa: F401
from net_alpha.db.connection import init_db
from net_alpha.pricing.cache import PriceCache
from net_alpha.pricing.provider import PriceFetchError, PriceProvider, Quote
from net_alpha.pricing.service import PricingService


class _FakeProvider(PriceProvider):
    def __init__(self, returns=None, raises=None):
        self.returns = returns or {}
        self.raises = raises
        self.calls: list[list[str]] = []

    def get_quotes(self, symbols):
        self.calls.append(list(symbols))
        if self.raises:
            raise self.raises
        return {s: self.returns[s] for s in symbols if s in self.returns}


def _engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 's.db'}")
    init_db(eng)
    return eng


def _quote(symbol, price):
    return Quote(symbol=symbol, price=Decimal(price), as_of=dt.datetime.now(dt.UTC), source="yahoo")


def test_disabled_service_returns_empty(tmp_path):
    cache = PriceCache(_engine(tmp_path))
    svc = PricingService(provider=_FakeProvider(), cache=cache, enabled=False)
    assert svc.get_prices(["SPY"]) == {}


def test_first_call_fetches_and_caches(tmp_path):
    cache = PriceCache(_engine(tmp_path))
    provider = _FakeProvider(returns={"SPY": _quote("SPY", "460.5")})
    svc = PricingService(provider=provider, cache=cache, enabled=True)
    prices = svc.get_prices(["SPY"])
    assert prices["SPY"].price == Decimal("460.5")
    # Second call hits cache, no extra provider call.
    svc.get_prices(["SPY"])
    assert len(provider.calls) == 1


def test_partial_cache_only_fetches_missing(tmp_path):
    cache = PriceCache(_engine(tmp_path))
    provider = _FakeProvider(returns={"QQQ": _quote("QQQ", "390.0")})
    svc = PricingService(provider=provider, cache=cache, enabled=True)
    cache.put_many([_quote("SPY", "460.5")])
    out = svc.get_prices(["SPY", "QQQ"])
    assert provider.calls == [["QQQ"]]
    assert out["SPY"].price == Decimal("460.5")
    assert out["QQQ"].price == Decimal("390.0")


def test_stale_cache_served_without_provider_call(tmp_path):
    """Stale cache entries are returned immediately and flagged via
    stale_symbols — the provider is NOT called on the read path. The
    refresh button is the only way to force a network fetch."""
    cache = PriceCache(_engine(tmp_path), ttl_seconds=0)  # everything stale immediately
    cache.put_many([_quote("SPY", "460.5")])
    provider = _FakeProvider(raises=PriceFetchError("net down"))
    svc = PricingService(provider=provider, cache=cache, enabled=True)
    out = svc.get_prices(["SPY"])
    assert out["SPY"].price == Decimal("460.5")
    assert provider.calls == []  # stale serve must not hit the network
    snap = svc.last_snapshot()
    assert snap.stale_symbols == ["SPY"]
    assert snap.degraded is False  # we didn't try to fetch, so no provider failure


def test_invalidate_and_refresh(tmp_path):
    cache = PriceCache(_engine(tmp_path))
    provider = _FakeProvider(returns={"SPY": _quote("SPY", "460.5")})
    svc = PricingService(provider=provider, cache=cache, enabled=True)
    svc.get_prices(["SPY"])
    assert len(provider.calls) == 1
    svc.refresh(["SPY"])
    assert len(provider.calls) == 2


def test_cold_fetch_failure_marks_degraded(tmp_path):
    """If a symbol has no cache row at all and the provider fails fetching
    it, the snapshot is marked degraded so the UI can surface the outage."""
    cache = PriceCache(_engine(tmp_path))
    failing_provider = _FakeProvider(raises=PriceFetchError("net down"))
    svc = PricingService(provider=failing_provider, cache=cache, enabled=True)
    out = svc.get_prices(["SPY"])
    assert out == {}
    assert svc.last_snapshot().degraded is True

    # Swap to a working provider — degraded must reset on next call.
    svc._provider = _FakeProvider(returns={"SPY": _quote("SPY", "461.0")})
    svc.get_prices(["SPY"])
    assert svc.last_snapshot().degraded is False
