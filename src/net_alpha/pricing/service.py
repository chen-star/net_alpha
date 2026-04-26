"""PricingService — orchestrates a PriceProvider with the PriceCache.

Public surface: get_prices, refresh, last_snapshot. Designed to be constructed
once per request (cheap) and never raise on price-fetch failures: instead, it
serves stale cache when present and reports `degraded=True` via last_snapshot().
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from loguru import logger

from net_alpha.pricing.cache import PriceCache
from net_alpha.pricing.provider import PriceFetchError, PriceProvider, Quote


@dataclass
class PricingSnapshot:
    """Diagnostic info about the most recent get_prices call."""

    fetched_at: dt.datetime | None = None
    source: str = ""
    degraded: bool = False
    stale_symbols: list[str] = field(default_factory=list)  # stale at cache-read; may be refreshed by provider below
    missing_symbols: list[str] = field(default_factory=list)


class PricingService:
    def __init__(self, *, provider: PriceProvider, cache: PriceCache, enabled: bool) -> None:
        self._provider = provider
        self._cache = cache
        self._enabled = enabled
        self._snapshot = PricingSnapshot()

    def last_snapshot(self) -> PricingSnapshot:
        return self._snapshot

    def get_prices(self, symbols: list[str]) -> dict[str, Quote]:
        """Return {symbol: Quote} for every symbol we have a price for (live or stale).

        When pricing is disabled, returns {}. When the provider fails, returns
        whatever stale cache exists.
        """
        if not self._enabled or not symbols:
            self._snapshot = PricingSnapshot()
            return {}

        cached = self._cache.get_many(symbols)
        fresh = {s: cq.quote for s, cq in cached.items() if not cq.stale}
        stale_only = {s: cq.quote for s, cq in cached.items() if cq.stale}
        to_fetch = [s for s in symbols if s not in fresh]

        snap = PricingSnapshot(stale_symbols=list(stale_only.keys()))

        if to_fetch:
            try:
                fetched = self._provider.get_quotes(to_fetch)
                self._cache.put_many(list(fetched.values()))
                fresh.update(fetched)
                snap.fetched_at = max((q.as_of for q in fetched.values()), default=None)
                if fetched:
                    snap.source = next(iter(fetched.values())).source
            except PriceFetchError as exc:
                logger.warning("pricing: provider failed: {}", exc)
                snap.degraded = True
                # Fall back to stale cache for the requested symbols.
                for s in to_fetch:
                    if s in stale_only:
                        fresh[s] = stale_only[s]

        snap.missing_symbols = [s for s in symbols if s not in fresh]
        self._snapshot = snap
        return fresh

    def refresh(self, symbols: list[str]) -> dict[str, Quote]:
        """Invalidate cached entries for symbols and re-fetch from the provider."""
        self._cache.invalidate(symbols)
        return self.get_prices(symbols)
