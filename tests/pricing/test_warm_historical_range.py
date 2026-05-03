from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

import net_alpha.db.tables as _tables  # noqa: F401
from net_alpha.db.migrations import migrate
from net_alpha.pricing.cache import PriceCache
from net_alpha.pricing.service import PricingService


@pytest.fixture
def memory_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.exec(text("DROP TABLE IF EXISTS historical_price_cache"))
        s.exec(text("DROP TABLE IF EXISTS position_targets"))
        s.exec(text("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', '11')"))
        s.commit()
    with Session(engine) as s:
        migrate(s)
    return engine


def test_warm_uses_one_bulk_call_per_symbol_not_per_date(memory_engine):
    """The lifetime equity-curve regression: per-(symbol,date) fetches blew up
    to thousands of rate-limited Yahoo calls. Warm must collapse the entire
    range into one bulk call per symbol."""
    cache = PriceCache(memory_engine)
    provider = MagicMock()
    # Provider returns a partial set of dates (only trading days exist).
    provider.get_historical_closes.return_value = {
        date(2025, 1, 2): Decimal("470.00"),
        date(2025, 1, 3): Decimal("471.50"),
    }
    svc = PricingService(provider=provider, cache=cache, enabled=True)

    svc.warm_historical_range(["SPY", "QQQ"], date(2025, 1, 1), date(2025, 1, 5))

    # One bulk call per symbol — NOT one per (symbol, date).
    assert provider.get_historical_closes.call_count == 2
    provider.get_historical_close.assert_not_called()


def test_warm_populates_cache_for_every_date_in_range(memory_engine):
    """Dates the provider didn't return must be negative-cached so subsequent
    lookups don't re-fetch (e.g. weekends, holidays)."""
    cache = PriceCache(memory_engine)
    provider = MagicMock()
    provider.get_historical_closes.return_value = {
        date(2025, 1, 2): Decimal("470.00"),  # Thu
        date(2025, 1, 3): Decimal("471.50"),  # Fri
        # Sat/Sun absent on purpose.
    }
    svc = PricingService(provider=provider, cache=cache, enabled=True)

    svc.warm_historical_range(["SPY"], date(2025, 1, 1), date(2025, 1, 5))

    # Subsequent get_historical_close hits cache for every date in range.
    provider.reset_mock()
    assert svc.get_historical_close("SPY", date(2025, 1, 2)) == Decimal("470.00")
    assert svc.get_historical_close("SPY", date(2025, 1, 4)) is None  # Sat — neg cached
    assert svc.get_historical_close("SPY", date(2025, 1, 5)) is None  # Sun — neg cached
    provider.get_historical_close.assert_not_called()


def test_warm_skips_already_cached_range(memory_engine):
    """Second warm over the same range must not re-fetch."""
    cache = PriceCache(memory_engine)
    provider = MagicMock()
    provider.get_historical_closes.return_value = {date(2025, 1, 2): Decimal("470.00")}
    svc = PricingService(provider=provider, cache=cache, enabled=True)

    svc.warm_historical_range(["SPY"], date(2025, 1, 1), date(2025, 1, 5))
    assert provider.get_historical_closes.call_count == 1

    svc.warm_historical_range(["SPY"], date(2025, 1, 1), date(2025, 1, 5))
    assert provider.get_historical_closes.call_count == 1  # no second fetch


def test_warm_does_not_negative_cache_when_provider_fails(memory_engine):
    """If the provider signals a fetch failure (rate-limit, network), we must
    NOT poison the cache with negatives — the user would never recover."""
    cache = PriceCache(memory_engine)
    provider = MagicMock()
    provider.get_historical_closes.return_value = None  # signals failure
    svc = PricingService(provider=provider, cache=cache, enabled=True)

    svc.warm_historical_range(["SPY"], date(2025, 1, 1), date(2025, 1, 5))

    # Cache untouched; the next single-fetch call still goes to the provider.
    provider.get_historical_close.return_value = Decimal("470.00")
    assert svc.get_historical_close("SPY", date(2025, 1, 2)) == Decimal("470.00")
    assert provider.get_historical_close.call_count == 1


def test_warm_no_op_when_disabled(memory_engine):
    cache = PriceCache(memory_engine)
    provider = MagicMock()
    svc = PricingService(provider=provider, cache=cache, enabled=False)

    svc.warm_historical_range(["SPY"], date(2025, 1, 1), date(2025, 1, 5))

    provider.get_historical_closes.assert_not_called()


def test_yahoo_get_historical_closes_returns_dict_keyed_by_date():
    """The bulk yfinance fetch returns one DataFrame; we parse it to a dict."""
    from unittest.mock import patch

    import pandas as pd

    df = pd.DataFrame(
        {"Close": [470.00, 471.50]},
        index=pd.DatetimeIndex([pd.Timestamp("2025-01-02"), pd.Timestamp("2025-01-03")]),
    )
    with patch("net_alpha.pricing.yahoo.yf") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = df
        mock_yf.Ticker.return_value = mock_ticker

        from net_alpha.pricing.yahoo import YahooPriceProvider

        provider = YahooPriceProvider()
        result = provider.get_historical_closes("SPY", date(2025, 1, 1), date(2025, 1, 5))

    assert result == {
        date(2025, 1, 2): Decimal("470.0"),
        date(2025, 1, 3): Decimal("471.5"),
    }


def test_yahoo_get_historical_closes_returns_none_on_exception():
    """Failure (rate-limit etc.) must signal None so the cache isn't poisoned."""
    from unittest.mock import patch

    with patch("net_alpha.pricing.yahoo.yf") as mock_yf:
        mock_yf.Ticker.side_effect = Exception("Too Many Requests. Rate limited.")

        from net_alpha.pricing.yahoo import YahooPriceProvider

        provider = YahooPriceProvider()
        result = provider.get_historical_closes("SPY", date(2025, 1, 1), date(2025, 1, 5))

    assert result is None
