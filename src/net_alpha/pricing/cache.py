"""SQLite-backed read-through cache for price quotes.

PriceCache.get returns CachedQuote(quote, stale) — stale=True when the row
exists but fetched_at is older than ttl_seconds. Callers decide whether to
serve stale data or refetch.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Engine

from net_alpha.pricing.provider import Quote


@dataclass(frozen=True)
class CachedQuote:
    quote: Quote
    stale: bool


class PriceCache:
    def __init__(self, engine: Engine, ttl_seconds: int = 900) -> None:
        self._engine = engine
        self._ttl = dt.timedelta(seconds=ttl_seconds)

    def get(self, symbol: str) -> CachedQuote | None:
        result = self.get_many([symbol])
        return result.get(symbol)

    def get_many(self, symbols: list[str]) -> dict[str, CachedQuote]:
        if not symbols:
            return {}
        placeholders = ",".join(f":s{i}" for i in range(len(symbols)))
        params = {f"s{i}": s for i, s in enumerate(symbols)}
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT symbol, price, as_of, fetched_at, source "
                    f"FROM price_cache WHERE symbol IN ({placeholders})"
                ),
                params,
            ).all()
        out: dict[str, CachedQuote] = {}
        now = dt.datetime.now(dt.UTC)
        for row_symbol, price, as_of, fetched_at, source in rows:
            quote = Quote(
                symbol=row_symbol,
                price=price,
                as_of=dt.datetime.fromisoformat(as_of),
                source=source,
            )
            stale = now - dt.datetime.fromisoformat(fetched_at) > self._ttl
            out[row_symbol] = CachedQuote(quote=quote, stale=stale)
        return out

    def put_many(self, quotes: list[Quote]) -> None:
        if not quotes:
            return
        now_iso = dt.datetime.now(dt.UTC).isoformat()
        with self._engine.begin() as conn:
            for q in quotes:
                conn.execute(
                    text(
                        "INSERT INTO price_cache(symbol, price, as_of, fetched_at, source) "
                        "VALUES (:symbol, :price, :as_of, :fetched_at, :source) "
                        "ON CONFLICT(symbol) DO UPDATE SET "
                        "price=:price, as_of=:as_of, fetched_at=:fetched_at, source=:source"
                    ),
                    {
                        "symbol": q.symbol,
                        "price": float(q.price),
                        "as_of": q.as_of.isoformat(),
                        "fetched_at": now_iso,
                        "source": q.source,
                    },
                )

    def invalidate(self, symbols: list[str]) -> None:
        if not symbols:
            return
        placeholders = ",".join(f":s{i}" for i in range(len(symbols)))
        params = {f"s{i}": s for i, s in enumerate(symbols)}
        with self._engine.begin() as conn:
            conn.execute(text(f"DELETE FROM price_cache WHERE symbol IN ({placeholders})"), params)
