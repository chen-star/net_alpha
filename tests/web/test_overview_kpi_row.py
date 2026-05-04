"""Lock the post-2026-05 KPI command-center layout on the Portfolio overview.

Single grid: hero (TOTAL ACCOUNT VALUE) anchors the left as a 4-col × 2-row
tile, and the four small KPIs (Total Return, Realized, Unrealized, Cash)
auto-flow into a 2×2 area to the right at lg:col-span-4 each.

Hero uses flex+justify-center so its content sits at the visual midpoint of
the stretched card (which matches the 2-stacked right column's height).
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


def test_hero_spans_four_cols_and_two_rows_on_lg(seeded_client):
    """Hero is the left anchor of the command-center header — 4 cols wide, 2 rows tall on lg+."""
    html = seeded_client.get("/portfolio/body").text
    block = _kpi_block(html)

    m = re.search(r'<div class="([^"]*)"\s+data-kpi-slot="hero"', block)
    assert m is not None, "hero kpi tile not found"
    classes = m.group(1)
    assert "lg:col-span-4" in classes, f"hero must be lg:col-span-4, got: {classes}"
    assert "lg:row-span-2" in classes, f"hero must be lg:row-span-2, got: {classes}"
    # Mobile fallback: stacks full width below lg.
    assert "col-span-12" in classes, f"hero must keep mobile col-span-12 fallback, got: {classes}"
    # Should not retain prior wide variants.
    assert "lg:col-span-8" not in classes, "hero should not be the old 8-col variant"
    assert "lg:col-span-12" not in classes, "hero should not span all 12 cols on lg"


def test_four_small_kpis_each_col_span_4(seeded_client):
    """Total Return + Realized + Unrealized + Cash each take 4/12 on lg+ — they
    auto-flow into the 2×2 area to the right of the row-span-2 hero."""
    html = seeded_client.get("/portfolio/body").text
    block = _kpi_block(html)

    for slot in ("total_return", "realized", "unrealized", "cash"):
        m = re.search(rf'<div class="([^"]*)"\s+data-kpi-slot="{slot}"', block)
        assert m is not None, f"slot {slot} not found"
        classes = m.group(1)
        assert "lg:col-span-4" in classes, f"{slot} must be lg:col-span-4, got: {classes}"
        assert "lg:col-span-3" not in classes, f"{slot} should no longer be lg:col-span-3"


def test_total_return_remains_plain_kpi(seeded_client):
    """Total Return does not use `kpi-promoted` — it sits in the small-KPI cluster
    with peer-level visual weight to Realized / Unrealized / Cash. (Carried over
    from the prior round; locks the demotion that shipped in b718936.)"""
    html = seeded_client.get("/portfolio/body").text
    block = _kpi_block(html)

    m = re.search(r'<div class="([^"]*)"\s+data-kpi-slot="total_return"', block)
    assert m is not None, "total_return tile not found"
    classes = m.group(1)
    assert "kpi-promoted" not in classes, (
        "total_return should remain a plain `kpi`; the promoted variant is reserved for the hero."
    )
    # Sanity: the base `kpi` class must still be there.
    assert "kpi" in classes.split()


def test_hero_content_is_vertically_centered(seeded_client):
    """Hero stretches to match the 2-stacked right column; flex+justify-center keeps
    the big number visually centered inside the card instead of clinging to the top
    with empty space below."""
    html = seeded_client.get("/portfolio/body").text
    block = _kpi_block(html)

    m = re.search(r'<div class="([^"]*)"\s+data-kpi-slot="hero"', block)
    assert m is not None, "hero kpi tile not found"
    classes = m.group(1).split()
    assert "flex" in classes, f"hero must use flex layout, got: {classes}"
    assert "flex-col" in classes, f"hero must use flex-col, got: {classes}"
    assert "justify-center" in classes, f"hero must vertically center content, got: {classes}"
