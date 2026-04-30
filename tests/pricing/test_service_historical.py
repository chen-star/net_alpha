from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

import net_alpha.db.tables as _tables  # noqa: F401 — registers all SQLModel table classes
from net_alpha.db.migrations import migrate
from net_alpha.pricing.cache import PriceCache
from net_alpha.pricing.service import PricingService


@pytest.fixture
def memory_engine():
    """In-memory SQLite with the full schema migrated up so historical_price_cache exists.

    SQLModel.metadata.create_all on a fresh DB causes migrate() to short-circuit at
    schema_version=0 without running _migrate_v11_to_v12 (which creates historical_price_cache).
    We follow the same pattern as tests/db/test_migration_v12.py: stamp v11, then migrate.
    """
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


def test_get_historical_close_caches_provider_result(memory_engine):
    cache = PriceCache(memory_engine)
    provider = MagicMock()
    provider.get_historical_close.return_value = Decimal("490.50")
    svc = PricingService(provider=provider, cache=cache, enabled=True)

    # 1st call hits the provider.
    assert svc.get_historical_close("SPY", date(2026, 1, 15)) == Decimal("490.50")
    assert provider.get_historical_close.call_count == 1

    # 2nd call is served from cache.
    assert svc.get_historical_close("SPY", date(2026, 1, 15)) == Decimal("490.50")
    assert provider.get_historical_close.call_count == 1


def test_get_historical_close_returns_none_when_disabled(memory_engine):
    cache = PriceCache(memory_engine)
    provider = MagicMock()
    svc = PricingService(provider=provider, cache=cache, enabled=False)

    assert svc.get_historical_close("SPY", date(2026, 1, 15)) is None
    provider.get_historical_close.assert_not_called()


def test_get_historical_close_caches_none_when_unavailable(memory_engine):
    """We negative-cache (don't repeatedly hammer Yahoo for a missing close)."""
    cache = PriceCache(memory_engine)
    provider = MagicMock()
    provider.get_historical_close.return_value = None
    svc = PricingService(provider=provider, cache=cache, enabled=True)

    assert svc.get_historical_close("XYZ", date(2026, 1, 15)) is None
    assert svc.get_historical_close("XYZ", date(2026, 1, 15)) is None
    # Provider hit only once — None was cached.
    assert provider.get_historical_close.call_count == 1
