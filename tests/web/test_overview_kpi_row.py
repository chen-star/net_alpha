"""Lock the post-2026-05 KPI row structure on the Portfolio overview.

Row 1: Hero alone, full-width on lg+ (col-span-12).
Row 2: 4 equal small KPIs — Total Return, Realized, Unrealized, Cash —
       each at lg:col-span-3.

Total Return is demoted from `kpi-promoted` (28px) to plain `kpi` (22px)
so it sits comfortably alongside the other three.
"""

from __future__ import annotations

import re
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


def _kpi_block(html: str) -> str:
    """Slice out everything between the kpis fragment markers."""
    start = html.find('id="portfolio-kpis"')
    assert start != -1, "portfolio-kpis container not found"
    return html[start : start + 16000]


def test_hero_is_full_width_on_lg(seeded_client):
    """Hero spans all 12 columns on lg+ — Total Return no longer rides shotgun."""
    html = seeded_client.get("/portfolio/body").text
    block = _kpi_block(html)

    m = re.search(r'<div class="([^"]*)"\s+data-kpi-slot="hero"', block)
    assert m is not None, "hero kpi tile not found"
    classes = m.group(1)
    assert "col-span-12" in classes, f"hero must be full-width, got classes: {classes}"
    assert "lg:col-span-8" not in classes, "hero should no longer share row 1 with another tile"


def test_four_small_kpis_each_col_span_3(seeded_client):
    """Total Return + Realized + Unrealized + Cash each take 3/12 on lg+."""
    html = seeded_client.get("/portfolio/body").text
    block = _kpi_block(html)

    for slot in ("total_return", "realized", "unrealized", "cash"):
        m = re.search(rf'<div class="([^"]*)"\s+data-kpi-slot="{slot}"', block)
        assert m is not None, f"slot {slot} not found"
        classes = m.group(1)
        assert "lg:col-span-3" in classes, f"{slot} must be lg:col-span-3, got: {classes}"
        assert "lg:col-span-4" not in classes, f"{slot} should no longer be lg:col-span-4"


def test_total_return_demoted_to_plain_kpi(seeded_client):
    """Total Return drops `kpi-promoted` so it matches the other small tiles."""
    html = seeded_client.get("/portfolio/body").text
    block = _kpi_block(html)

    m = re.search(r'<div class="([^"]*)"\s+data-kpi-slot="total_return"', block)
    assert m is not None, "total_return tile not found"
    classes = m.group(1)
    assert "kpi-promoted" not in classes, (
        "total_return should no longer use the promoted variant; it now sits in row 2 with the other small KPIs"
    )
    # Sanity: the base `kpi` class must still be there.
    assert "kpi" in classes.split()
