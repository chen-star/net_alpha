"""Deterministic, network-free price provider for web tests.

Web tests must not reach Yahoo (the ``--run-network`` gate in
``tests/conftest.py`` keeps the suite offline). But the pricing service only
serves cached/historical prices when it is *enabled* — a disabled service
returns ``{}`` / ``None`` and ignores the cache entirely, which leaves the
Portfolio equity curve unpriced and breaks any test that seeds ``price_cache``.

So web fixtures keep pricing enabled and swap the real ``YahooPriceProvider``
for this fake: cache hits are served as usual, and cache *misses* resolve to a
flat deterministic close instead of a network call.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from net_alpha.pricing.provider import Quote
from net_alpha.pricing.yahoo import YahooPriceProvider


class OfflineFakeProvider(YahooPriceProvider):
    """Returns a flat close for every symbol/date — no network I/O.

    Subclasses :class:`YahooPriceProvider` (rather than the bare ABC) so tests
    that patch ``YahooPriceProvider.fetch_splits`` still take effect — only the
    network-fetching read methods below are overridden. ``YahooPriceProvider``
    has no custom ``__init__`` and reaches the network only inside its methods,
    so instantiating it here is free and offline.
    """

    _PRICE = Decimal("150.00")

    def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        now = dt.datetime.now(dt.UTC)
        return {s: Quote(symbol=s, price=self._PRICE, as_of=now, source="fake") for s in symbols}

    def get_historical_close(self, symbol: str, on: dt.date) -> Decimal | None:
        return self._PRICE

    def get_historical_closes(self, symbol: str, start: dt.date, end: dt.date) -> dict[dt.date, Decimal]:
        out: dict[dt.date, Decimal] = {}
        d = start
        while d <= end:
            if d.weekday() < 5:  # weekdays only — mirrors real trading-day cadence
                out[d] = self._PRICE
            d += dt.timedelta(days=1)
        return out
