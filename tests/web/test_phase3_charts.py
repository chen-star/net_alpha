"""Phase 3 chart polish (§5.12, §6.2 P6/P7).

Equity and cash curves are rendered in the /portfolio/body HTMX fragment.
Tests hit that endpoint directly (the page shell only includes the template
wrapper; the charts are lazy-loaded by HTMX on the real browser, so the
fragment endpoint is the correct assertion surface for chart markup).
"""

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
def chart_client(tmp_path):
    """Client with a seeded trade so charts render (non-empty data required)."""
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


def test_equity_chart_options_set_hide_overlapping_labels(chart_client: TestClient):
    """The equity-curve x-axis options enable overlap suppression so month
    labels don't double up at default tick density (P6)."""
    resp = chart_client.get("/portfolio/body")
    html = resp.text
    assert "hideOverlappingLabels" in html


def test_cash_chart_solid_is_cash_balance_dashed_is_net_contributed(chart_client: TestClient):
    """Spec §5.12: solid → cash balance; dashed → net contributed (P7).
    Assert via stable data-* attributes on the cash-curve container."""
    resp = chart_client.get("/portfolio/body")
    html = resp.text
    assert 'data-series-solid="cash_balance"' in html
    assert 'data-series-dashed="net_contributed"' in html
