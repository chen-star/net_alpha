"""Tests for cached_underlying_prices — the §1092 price-snapshot helper."""

import datetime as dt
from decimal import Decimal

from sqlmodel import create_engine

import net_alpha.db.tables as _tables  # noqa: F401 — registers SQLModel tables
from net_alpha.db.connection import init_db
from net_alpha.db.repository import Repository
from net_alpha.pricing.cache import PriceCache
from net_alpha.pricing.provider import Quote
from net_alpha.section_1092.prices import cached_underlying_prices


def _engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'cache.db'}")
    init_db(eng)
    return eng


def _quote(symbol: str, price: str) -> Quote:
    return Quote(
        symbol=symbol,
        price=Decimal(price),
        as_of=dt.datetime(2026, 5, 9, 14, 30, tzinfo=dt.UTC),
        source="yahoo",
    )


def test_returns_empty_when_no_tickers(tmp_path):
    repo = Repository(_engine(tmp_path))
    assert cached_underlying_prices(repo, []) == {}


def test_returns_empty_when_cache_is_empty(tmp_path):
    repo = Repository(_engine(tmp_path))
    assert cached_underlying_prices(repo, ["AAPL", "MSFT"]) == {}


def test_returns_decimal_prices_for_cached_tickers(tmp_path):
    eng = _engine(tmp_path)
    PriceCache(eng).put_many([_quote("AAPL", "180.50"), _quote("MSFT", "420.10")])
    repo = Repository(eng)

    out = cached_underlying_prices(repo, ["AAPL", "MSFT", "GOOG"])
    assert out == {"AAPL": Decimal("180.50"), "MSFT": Decimal("420.10")}
    assert "GOOG" not in out  # uncached ticker drops out, no error


def test_dedups_and_filters_empty_tickers(tmp_path):
    eng = _engine(tmp_path)
    PriceCache(eng).put_many([_quote("AAPL", "180.50")])
    repo = Repository(eng)

    out = cached_underlying_prices(repo, ["AAPL", "AAPL", "", "AAPL"])
    assert out == {"AAPL": Decimal("180.50")}
