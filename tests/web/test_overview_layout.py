"""Layout regression tests for the Portfolio overview body fragment."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.domain import ImportRecord, Trade
from net_alpha.web.app import create_app


@pytest.fixture
def seeded_client(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)
    account = repo.get_or_create_account("Schwab", "Tax")
    trade = Trade(
        account="Schwab/Tax",
        date=date(2026, 1, 2),
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
        imported_at=datetime(2026, 1, 2, tzinfo=UTC),
        trade_count=1,
    )
    repo.add_import(account, record, [trade])
    return TestClient(create_app(settings), raise_server_exceptions=False)


def test_equity_and_cash_curves_use_two_thirds_one_third_split(seeded_client):
    """Equity is the primary chart; cash is operational context. The grid
    that holds them should give equity roughly two-thirds of the row width."""
    html = seeded_client.get("/portfolio/body").text
    # The body uses an inline grid-template-columns style. The string we want
    # is the one wrapping the equity-curve and cash-curve panels.
    assert 'grid-template-columns: 2fr 1fr;' in html
    # And the old 50/50 string is gone from the equity/cash row context.
    # (We allow `1fr 1fr` elsewhere on the page if any other row uses it.)
    equity_idx = html.find('id="portfolio-equity"')
    assert equity_idx > 0
    # Walk back 400 chars and confirm the nearest grid-template-columns is 2fr 1fr.
    preceding = html[max(0, equity_idx - 400):equity_idx]
    assert 'grid-template-columns: 2fr 1fr;' in preceding
    assert 'grid-template-columns: 1fr 1fr;' not in preceding
