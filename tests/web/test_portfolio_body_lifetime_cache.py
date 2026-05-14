"""Cache regression test for the lifetime equity-curve helper.

The expensive ``_build_lifetime_account_points`` helper must be called at most
once regardless of how many period-switches the user makes within the same
fragment-revision window.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from unittest.mock import patch

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
    """TestClient wired to a temp DB that has one buy trade dated in the past.

    This ensures ``_build_lifetime_account_points`` actually has data to
    process, so the real implementation runs and the cache can be exercised.
    """
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)

    # Seed an account + import + trade dated two years ago.
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
    return TestClient(app, raise_server_exceptions=False)


def test_lifetime_curve_built_at_most_once_across_period_switches(client_with_trade):
    """Three body requests across two distinct periods must build the lifetime
    curve at most once — the cache should amortize it after the first call.
    """
    with patch(
        "net_alpha.web.routes.portfolio._build_lifetime_account_points",
        wraps=__import__(
            "net_alpha.web.routes.portfolio", fromlist=["_build_lifetime_account_points"]
        )._build_lifetime_account_points,
    ) as spy:
        past_year = date.today().year - 1

        # First request: YTD
        r1 = client_with_trade.get("/portfolio/body?period=ytd")
        assert r1.status_code == 200

        # Second request: a past year (different period)
        r2 = client_with_trade.get(f"/portfolio/body?period={past_year}")
        assert r2.status_code == 200

        # Third request: YTD again
        r3 = client_with_trade.get("/portfolio/body?period=ytd")
        assert r3.status_code == 200

        # The lifetime builder should have been called at most once — the cache
        # amortizes it across period switches within the same revision window.
        assert spy.call_count <= 1, (
            f"_build_lifetime_account_points called {spy.call_count} times; expected ≤1 (cached after first call)"
        )
