"""Tests for YahooPriceProvider.

The unit test uses a stub instead of hitting the network. The network-gated
test below runs only when --run-network is passed.
"""

from decimal import Decimal
from unittest.mock import patch

import pytest

from net_alpha.pricing.provider import PriceFetchError
from net_alpha.pricing.yahoo import YahooPriceProvider


class _FakeTicker:
    def __init__(self, symbol: str, price: float | None) -> None:
        self.info = {"regularMarketPrice": price} if price is not None else {}
        self.symbol = symbol


def test_get_quotes_returns_present_symbols_only():
    provider = YahooPriceProvider()
    fake = {"SPY": _FakeTicker("SPY", 460.5), "TSLA": _FakeTicker("TSLA", None)}
    with patch("net_alpha.pricing.yahoo.yf.Ticker", side_effect=lambda s: fake[s]):
        quotes = provider.get_quotes(["SPY", "TSLA"])
    assert set(quotes.keys()) == {"SPY"}
    assert quotes["SPY"].price == Decimal("460.5")
    assert quotes["SPY"].source == "yahoo"
    assert quotes["SPY"].as_of.tzinfo is not None


def test_get_quotes_empty_symbols_returns_empty():
    provider = YahooPriceProvider()
    assert provider.get_quotes([]) == {}


def test_get_quotes_wraps_systemic_errors_in_price_fetch_error():
    """A failure outside the per-symbol loop (e.g. clock failure) raises PriceFetchError."""
    provider = YahooPriceProvider()
    with patch("net_alpha.pricing.yahoo.dt.datetime") as mock_dt:
        mock_dt.now.side_effect = RuntimeError("clock failure")
        with pytest.raises(PriceFetchError) as excinfo:
            provider.get_quotes(["SPY"])
    assert "clock failure" in str(excinfo.value)
    assert excinfo.value.symbols == ["SPY"]


def test_get_quotes_per_symbol_error_is_skipped_not_raised():
    """A failure fetching one symbol is logged and skipped; other symbols still return."""
    provider = YahooPriceProvider()
    fake_good = _FakeTicker("AAPL", 200.0)

    def ticker_factory(symbol: str):
        if symbol == "SPY":
            raise RuntimeError("connection refused")
        return fake_good

    with patch("net_alpha.pricing.yahoo.yf.Ticker", side_effect=ticker_factory):
        quotes = provider.get_quotes(["SPY", "AAPL"])
    assert "SPY" not in quotes
    assert "AAPL" in quotes


@pytest.mark.network
def test_yahoo_live_fetch_for_spy():
    """Live network test — requires --run-network. Skipped by default."""
    provider = YahooPriceProvider()
    quotes = provider.get_quotes(["SPY"])
    assert "SPY" in quotes
    assert quotes["SPY"].price > 0
