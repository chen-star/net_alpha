import datetime as dt
from decimal import Decimal

import pytest
from pydantic import ValidationError

from net_alpha.pricing.provider import PriceFetchError, PriceProvider, Quote


def test_quote_holds_required_fields():
    q = Quote(
        symbol="SPY",
        price=Decimal("460.5"),
        as_of=dt.datetime(2026, 4, 26, 14, 30, tzinfo=dt.UTC),
        source="yahoo",
    )
    assert q.symbol == "SPY"
    assert q.price == Decimal("460.5")
    assert q.source == "yahoo"


def test_quote_rejects_missing_fields():
    with pytest.raises(ValidationError):
        Quote(symbol="SPY")


def test_provider_is_abstract():
    with pytest.raises(TypeError):
        PriceProvider()


def test_quote_is_immutable():
    q = Quote(
        symbol="SPY",
        price=Decimal("460.5"),
        as_of=dt.datetime(2026, 4, 26, 14, 30, tzinfo=dt.UTC),
        source="yahoo",
    )
    with pytest.raises(ValidationError):
        q.price = Decimal("999")


def test_quote_rejects_naive_datetime():
    with pytest.raises(ValidationError):
        Quote(symbol="SPY", price=Decimal("460.5"), as_of=dt.datetime(2026, 4, 26, 14, 30), source="yahoo")


def test_price_fetch_error_carries_context():
    err = PriceFetchError("timeout", symbols=["SPY", "QQQ"])
    assert "timeout" in str(err)
    assert err.symbols == ["SPY", "QQQ"]
