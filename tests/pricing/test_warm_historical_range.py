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


def test_warm_negative_caches_only_weekends_not_weekday_misses(memory_engine):
    """Dates absent from a partial bulk response must NOT be negative-cached
    if they're weekdays. Weekends are authoritatively closed, so caching None
    for Sat/Sun is fine — but caching None for a real trading day a partial
    yfinance response missed leaves the user with a permanently undercounted
    starting value (which inflates Total Return). Trading-day misses must
    stay _MISS so the single-fetch fallback can recover them.
    """
    cache = PriceCache(memory_engine)
    provider = MagicMock()
    # Bulk response covers Thu+Fri but not the in-range Sat/Sun, AND drops a
    # real trading day (Mon Jan 6) — simulating the partial-response failure
    # mode that previously poisoned the cache.
    provider.get_historical_closes.return_value = {
        date(2025, 1, 2): Decimal("470.00"),  # Thu
        date(2025, 1, 3): Decimal("471.50"),  # Fri
        # Sat/Sun absent (correct: market closed)
        # Mon Jan 6 absent (incorrect: real trading day, partial response)
    }
    svc = PricingService(provider=provider, cache=cache, enabled=True)

    svc.warm_historical_range(["SPY"], date(2025, 1, 1), date(2025, 1, 6))

    # Weekends are negative-cached.
    assert cache.historical_get("SPY", date(2025, 1, 4)) is None
    assert cache.historical_get("SPY", date(2025, 1, 5)) is None
    # Trading day Jan 1 (a Wed but New Year's Day, pre-range) AND Mon Jan 6
    # are NOT negative-cached — they remain _MISS so a later single-fetch
    # can populate them once yfinance is reachable again.
    from net_alpha.pricing.cache import _MISS

    assert cache.historical_get("SPY", date(2025, 1, 1)) is _MISS  # Wed (holiday)
    assert cache.historical_get("SPY", date(2025, 1, 6)) is _MISS  # Mon (real trading day)
    # Real returns are cached normally.
    assert cache.historical_get("SPY", date(2025, 1, 2)) == Decimal("470.00")
    assert cache.historical_get("SPY", date(2025, 1, 3)) == Decimal("471.50")


def test_warm_skips_already_cached_range(memory_engine):
    """Second warm over a range whose every date is now cached (positive
    closes for trading days, negative for weekends) must not re-fetch.

    This is the steady-state behavior: once the warmer + the single-fetch
    fallback have fully populated a range, subsequent warms are no-ops.
    """
    cache = PriceCache(memory_engine)
    provider = MagicMock()
    provider.get_historical_closes.return_value = {
        # All trading days in [Mon Jan 6 .. Fri Jan 10] covered.
        date(2025, 1, 6): Decimal("470.00"),
        date(2025, 1, 7): Decimal("470.50"),
        date(2025, 1, 8): Decimal("471.00"),
        date(2025, 1, 9): Decimal("471.50"),
        date(2025, 1, 10): Decimal("472.00"),
    }
    svc = PricingService(provider=provider, cache=cache, enabled=True)

    svc.warm_historical_range(["SPY"], date(2025, 1, 6), date(2025, 1, 12))
    assert provider.get_historical_closes.call_count == 1

    svc.warm_historical_range(["SPY"], date(2025, 1, 6), date(2025, 1, 12))
    assert provider.get_historical_closes.call_count == 1  # all dates cached, no refetch


def test_warm_refetches_when_cache_has_unfilled_trading_days(memory_engine):
    """A second warm over a range where some weekdays are still _MISS (e.g.
    a partial first response) must re-fetch — that's the whole point of not
    poisoning the cache with negatives on real trading days. Self-healing.
    """
    cache = PriceCache(memory_engine)
    provider = MagicMock()
    # First response is partial: missing Mon Jan 6 (a real trading day).
    provider.get_historical_closes.return_value = {
        date(2025, 1, 7): Decimal("470.50"),
        date(2025, 1, 8): Decimal("471.00"),
    }
    svc = PricingService(provider=provider, cache=cache, enabled=True)

    svc.warm_historical_range(["SPY"], date(2025, 1, 6), date(2025, 1, 8))
    assert provider.get_historical_closes.call_count == 1

    # Jan 6 is still _MISS — warm again, expect a re-fetch.
    svc.warm_historical_range(["SPY"], date(2025, 1, 6), date(2025, 1, 8))
    assert provider.get_historical_closes.call_count == 2


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
