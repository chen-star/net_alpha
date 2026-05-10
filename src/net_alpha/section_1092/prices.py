"""Cached underlying-price lookup for §1092 detection.

Best-effort wrapper around `pricing.cache.PriceCache.get_many()` that returns
a ticker → Decimal map. Used by the CLI surfaces (`straddles`, `sim`) to feed
the detector's QCC test on covered-call groups. Tickers missing from the
local cache drop out, and the detector emits a "QCC test skipped" reasoning
on those groups.

Read-only — never triggers a network fetch. Live refresh is the job of
`pricing.service.PricingService` and the background `price_refresh` job.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from net_alpha.db.repository import Repository


def cached_underlying_prices(repo: Repository, tickers: Iterable[str]) -> dict[str, Decimal]:
    syms = sorted({t for t in tickers if t})
    if not syms:
        return {}
    try:
        from net_alpha.pricing.cache import PriceCache

        cache = PriceCache(repo.engine)
        cached = cache.get_many(syms)
    except Exception:  # noqa: BLE001 — cache is best-effort; never block detection on price lookup
        return {}
    return {sym: Decimal(str(cq.quote.price)) for sym, cq in cached.items()}
