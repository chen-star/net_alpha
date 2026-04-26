import datetime as dt
from decimal import Decimal

from sqlalchemy import text
from sqlmodel import create_engine

import net_alpha.db.tables as _tables  # noqa: F401
from net_alpha.db.connection import init_db
from net_alpha.pricing.cache import CachedQuote, PriceCache  # noqa: F401 — CachedQuote is part of the tested public API
from net_alpha.pricing.provider import Quote


def _engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'cache.db'}")
    init_db(eng)
    return eng


def _quote(symbol="SPY", price="460.5", as_of=None):
    return Quote(
        symbol=symbol,
        price=Decimal(price),
        as_of=as_of or dt.datetime(2026, 4, 26, 14, 30, tzinfo=dt.UTC),
        source="yahoo",
    )


def test_cache_miss_returns_none(tmp_path):
    cache = PriceCache(_engine(tmp_path), ttl_seconds=900)
    assert cache.get("SPY") is None


def test_cache_put_then_get_within_ttl(tmp_path):
    cache = PriceCache(_engine(tmp_path), ttl_seconds=900)
    cache.put_many([_quote()])
    cached = cache.get("SPY")
    assert cached is not None
    assert cached.quote.symbol == "SPY"
    assert cached.quote.price == Decimal("460.5")
    assert cached.stale is False


def test_cache_returns_stale_after_ttl(tmp_path):
    cache = PriceCache(_engine(tmp_path), ttl_seconds=1)
    cache.put_many([_quote()])
    # Force fetched_at into the past by overriding the stored row.
    with cache._engine.begin() as conn:
        conn.execute(
            text("UPDATE price_cache SET fetched_at=:t WHERE symbol='SPY'"),
            {"t": (dt.datetime.now(dt.UTC) - dt.timedelta(seconds=10)).isoformat()},
        )
    cached = cache.get("SPY")
    assert cached is not None
    assert cached.stale is True


def test_cache_invalidate_drops_entry(tmp_path):
    cache = PriceCache(_engine(tmp_path), ttl_seconds=900)
    cache.put_many([_quote()])
    cache.invalidate(["SPY"])
    assert cache.get("SPY") is None


def test_cache_get_many_returns_only_present(tmp_path):
    cache = PriceCache(_engine(tmp_path), ttl_seconds=900)
    cache.put_many([_quote("SPY"), _quote("QQQ", "390.0")])
    out = cache.get_many(["SPY", "QQQ", "TSLA"])
    assert set(out.keys()) == {"SPY", "QQQ"}
    assert out["QQQ"].quote.price == Decimal("390.0")
