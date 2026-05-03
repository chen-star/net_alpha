"""SQLite-backed read-through cache for price quotes.

PriceCache.get returns CachedQuote(quote, stale) — stale=True when the row
exists but fetched_at is older than ttl_seconds. Callers decide whether to
serve stale data or refetch.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import Engine

from net_alpha.pricing.provider import Quote


class _Sentinel:
    pass


_MISS: _Sentinel = _Sentinel()


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
                    f"SELECT symbol, price, as_of, fetched_at, source FROM price_cache WHERE symbol IN ({placeholders})"
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

    def historical_get(self, symbol: str, on: dt.date) -> Decimal | None | _Sentinel:
        """Return the cached close price for (symbol, on). Returns:
        - Decimal      → cached value
        - None         → cached negative (provider previously couldn't fetch)
        - _MISS        → no row at all (caller should fetch)
        """
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT close_price FROM historical_price_cache WHERE symbol = :s AND on_date = :d"),
                {"s": symbol, "d": on.isoformat()},
            ).first()
        if row is None:
            return _MISS
        if row[0] is None:
            return None
        return Decimal(str(row[0]))

    def historical_put(self, symbol: str, on: dt.date, close: Decimal | None) -> None:
        """Insert or replace the cached close (None means negative cache)."""
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO historical_price_cache(symbol, on_date, close_price, fetched_at) "
                    "VALUES (:s, :d, :c, :f) "
                    "ON CONFLICT(symbol, on_date) DO UPDATE SET "
                    "close_price = excluded.close_price, fetched_at = excluded.fetched_at"
                ),
                {
                    "s": symbol,
                    "d": on.isoformat(),
                    "c": str(close) if close is not None else None,
                    "f": dt.datetime.now(dt.UTC).isoformat(),
                },
            )

    def historical_dates_in_range(self, symbol: str, start: dt.date, end: dt.date) -> set[dt.date]:
        """Return the set of cached dates for `symbol` within [start, end]
        inclusive (used by the warm path to skip already-populated ranges)."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT on_date FROM historical_price_cache "
                    "WHERE symbol = :s AND on_date >= :start AND on_date <= :end"
                ),
                {"s": symbol, "start": start.isoformat(), "end": end.isoformat()},
            ).all()
        return {dt.date.fromisoformat(r[0]) for r in rows}

    def historical_put_many(self, rows: list[tuple[str, dt.date, Decimal | None]]) -> None:
        """Bulk upsert closes. None close means negative cache."""
        if not rows:
            return
        now_iso = dt.datetime.now(dt.UTC).isoformat()
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO historical_price_cache(symbol, on_date, close_price, fetched_at) "
                    "VALUES (:s, :d, :c, :f) "
                    "ON CONFLICT(symbol, on_date) DO UPDATE SET "
                    "close_price = excluded.close_price, fetched_at = excluded.fetched_at"
                ),
                [
                    {
                        "s": symbol,
                        "d": d.isoformat(),
                        "c": str(close) if close is not None else None,
                        "f": now_iso,
                    }
                    for symbol, d, close in rows
                ],
            )
