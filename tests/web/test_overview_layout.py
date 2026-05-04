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


def test_equity_and_cash_curves_use_three_to_two_split(seeded_client):
    """Equity is the primary chart; cash is operational context. The row
    holding them is 3:2 (60/40) — wider than the legacy 2:1 split so the
    cash + contributions chart has room to read, but still keeps equity
    visually dominant. The allocation row below stays at 2:1."""
    html = seeded_client.get("/portfolio/body").text
    # The new equity/cash row uses the 3:2 ratio.
    assert "grid-template-columns: 3fr 2fr;" in html
    # Walk back from the equity panel and confirm the nearest
    # grid-template-columns is the new 3:2 (and NOT the legacy 2:1 or 1:1).
    equity_idx = html.find('id="portfolio-equity"')
    assert equity_idx > 0
    preceding = html[max(0, equity_idx - 400) : equity_idx]
    assert "grid-template-columns: 3fr 2fr;" in preceding
    assert "grid-template-columns: 2fr 1fr;" not in preceding
    assert "grid-template-columns: 1fr 1fr;" not in preceding
    # The allocation row below still uses 2:1 — confirm that lock is intact.
    alloc_idx = html.find('id="portfolio-allocation"')
    assert alloc_idx > equity_idx
    alloc_preceding = html[max(0, alloc_idx - 400) : alloc_idx]
    assert "grid-template-columns: 2fr 1fr;" in alloc_preceding


def test_toolbar_overflow_menu_holds_sync_splits(seeded_client):
    """Sync splits is admin-grade — it belongs behind a kebab menu, not as
    a primary inline button competing with Period and Account."""
    html = seeded_client.get("/").text
    # Kebab menu trigger uses the existing ellipsis icon + Alpine pattern.
    assert 'data-testid="toolbar-overflow"' in html
    # Sync splits is reachable inside the menu, not as a top-level button.
    overflow_idx = html.find('data-testid="toolbar-overflow"')
    assert overflow_idx > 0
    # The Sync-splits markup (POST to /splits/sync) must live AFTER the
    # overflow trigger, inside the dropdown.
    sync_idx = html.find('hx-post="/splits/sync', overflow_idx)
    assert sync_idx > 0, "Sync splits action must live inside the overflow menu"


def test_toolbar_does_not_show_inline_yahoo_disclaimer(seeded_client):
    """The 'Prices via Yahoo (~15 min delay)' inline span inside the toolbar
    is gone — that information now lives in the freshness chip tooltip.

    (The global footer disclosure on base.html is unrelated and intentionally
    preserved — it provides ambient disclosure on pages that don't render the
    toolbar/chip, e.g. Sim, Tax, Imports.)"""
    html = seeded_client.get("/").text
    # Locate the toolbar form. The toolbar is a kpi-card form that contains
    # the period select.
    freshness_idx = html.find('data-testid="freshness-chip"')
    assert freshness_idx > 0
    form_start = html.rfind("<form", 0, freshness_idx)
    form_end = html.index("</form>", freshness_idx)
    toolbar_html = html[form_start:form_end]
    assert "Prices via Yahoo (~15 min delay)" not in toolbar_html


def test_freshness_chip_tooltip_mentions_provider_and_delay(seeded_client):
    """The freshness chip absorbs the provider + delay disclaimer in its
    title= so users still discover where the prices come from."""
    html = seeded_client.get("/").text
    # Find the chip's opening tag and confirm its title includes both
    # 'Yahoo' and 'delay' (case-insensitive).
    assert 'data-testid="freshness-chip"' in html
    chip_idx = html.find('data-testid="freshness-chip"')
    tag_start = html.rfind("<button", 0, chip_idx)
    tag_end = html.index(">", chip_idx)
    chip_tag = html[tag_start : tag_end + 1].lower()
    assert "yahoo" in chip_tag
    assert "delay" in chip_tag
