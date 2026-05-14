"""Regression test for body load latency.

The lifetime equity-curve brush strip was removed entirely (it duplicated the
Period dropdown and the lifetime account-value compute it required dominated
cold body latency). This test pins that the helper that drove that cost has
been deleted, and that body requests never touch the historical-prices warm
path. If a future change reintroduces it without the lazy-load discipline,
this test should be the canary.
"""

from __future__ import annotations

import os
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.domain import ImportRecord, Trade
from net_alpha.web.app import create_app

# Skip scheduler startup — it requires asyncio event loop not available in
# sync test environments.
os.environ.setdefault("NETALPHA_SKIP_SCHEDULER", "1")


@pytest.fixture
def client_with_trade(tmp_path):
    """TestClient wired to a temp DB that has one buy trade dated in the past."""
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)

    account = repo.get_or_create_account("Schwab", "Tax")
    trade = Trade(
        account="Schwab/Tax",
        date=date(date.today().year - 2, 6, 15),
        ticker="AAPL",
        action="Buy",
        quantity=10.0,
        proceeds=None,
        cost_basis=1800.0,
    )
    record = ImportRecord(
        account_id=account.id,
        csv_filename="seed.csv",
        csv_sha256="sha-seed",
        imported_at=datetime.now(),
        trade_count=1,
    )
    repo.add_import(account, record, [trade])

    app = create_app(settings)
    return TestClient(app)


def test_lifetime_curve_helpers_removed():
    """The expensive ``_build_lifetime_account_points`` /
    ``_get_or_compute_lifetime_curve`` helpers are gone with the brush. If
    they reappear, also reintroduce a cache or lazy-load discipline so cold
    body latency doesn't regress."""
    from net_alpha.web.routes import portfolio as P

    assert not hasattr(P, "_build_lifetime_account_points")
    assert not hasattr(P, "_get_or_compute_lifetime_curve")


def test_body_does_not_fan_out_historical_prices(client_with_trade, monkeypatch):
    """The body endpoint must not call the historical-prices warm path,
    which was the dominant cold-load cost when the brush existed."""
    from net_alpha.pricing.service import PricingService

    called = {"n": 0}
    original = PricingService.warm_historical_range

    def spy(self, *args, **kwargs):
        called["n"] += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(PricingService, "warm_historical_range", spy)

    r1 = client_with_trade.get("/portfolio/body?period=ytd")
    assert r1.status_code == 200
    r2 = client_with_trade.get(f"/portfolio/body?period={date.today().year - 1}")
    assert r2.status_code == 200
    # Body uses the YTD account-value series, which does warm — once per
    # period. But it should NOT warm a second time for the lifetime brush
    # (the brush is gone). Two requests on two periods → ≤ 2 warm calls.
    assert called["n"] <= 2, f"warm_historical_range called {called['n']}× (expected ≤2)"
