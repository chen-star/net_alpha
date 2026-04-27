"""YahooPriceProvider.fetch_splits parses yfinance.Ticker.splits."""

from datetime import date
from unittest.mock import patch

import pandas as pd

from net_alpha.pricing.yahoo import YahooPriceProvider


class _FakeTicker:
    def __init__(self, splits_series: pd.Series) -> None:
        self.splits = splits_series


def test_fetch_splits_returns_split_events_in_date_order():
    provider = YahooPriceProvider()
    series = pd.Series(
        [4.0, 7.0],
        index=pd.to_datetime(["2020-08-31", "2014-06-09"]),
    )
    fake = _FakeTicker(series)
    with patch("net_alpha.pricing.yahoo.yf.Ticker", return_value=fake):
        events = provider.fetch_splits("AAPL")

    assert len(events) == 2
    assert events[0].split_date == date(2014, 6, 9)
    assert events[0].ratio == 7.0
    assert events[1].split_date == date(2020, 8, 31)
    assert events[1].ratio == 4.0


def test_fetch_splits_empty_when_no_splits():
    provider = YahooPriceProvider()
    fake = _FakeTicker(pd.Series([], dtype=float))
    with patch("net_alpha.pricing.yahoo.yf.Ticker", return_value=fake):
        events = provider.fetch_splits("AAPL")
    assert events == []


def test_fetch_splits_swallows_per_symbol_error():
    """Network/parse error for one symbol returns []; doesn't raise."""
    provider = YahooPriceProvider()
    with patch("net_alpha.pricing.yahoo.yf.Ticker", side_effect=RuntimeError("boom")):
        events = provider.fetch_splits("BAD")
    assert events == []
