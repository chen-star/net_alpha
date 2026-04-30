from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from net_alpha.pricing.yahoo import YahooPriceProvider


@patch("net_alpha.pricing.yahoo.yf")
def test_get_historical_close_returns_decimal(mock_yf):
    # yfinance returns a DataFrame with a 'Close' column indexed by date
    import pandas as pd

    df = pd.DataFrame(
        {"Close": [490.50]},
        index=pd.DatetimeIndex([pd.Timestamp("2026-01-15")]),
    )
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = df
    mock_yf.Ticker.return_value = mock_ticker

    provider = YahooPriceProvider()
    close = provider.get_historical_close("SPY", date(2026, 1, 15))

    assert close == Decimal("490.50")


@patch("net_alpha.pricing.yahoo.yf")
def test_get_historical_close_returns_none_when_no_row(mock_yf):
    import pandas as pd

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = pd.DataFrame()
    mock_yf.Ticker.return_value = mock_ticker

    provider = YahooPriceProvider()
    assert provider.get_historical_close("SPY", date(2026, 1, 15)) is None


@patch("net_alpha.pricing.yahoo.yf")
def test_get_historical_close_returns_none_on_exception(mock_yf):
    mock_yf.Ticker.side_effect = Exception("network down")

    provider = YahooPriceProvider()
    assert provider.get_historical_close("SPY", date(2026, 1, 15)) is None
