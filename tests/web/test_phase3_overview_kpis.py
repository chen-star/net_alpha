"""Phase 3 Overview clutter removal + KPI restructure (§4.1, §6.2 P1/P3/P5/P9).

The Overview body is lazy-loaded by HTMX from /portfolio/body. Tests that
assert body-level content (KPIs, charts, panels) use that fragment endpoint.
Tests that assert toolbar-level content hit / directly, since the toolbar
is rendered eagerly in portfolio.html (only when imports exist, so we seed).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.web.app import create_app


@pytest.fixture
def seeded_client(tmp_path):
    """Client with one import so the toolbar + body both render."""
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)
    repo.get_or_create_account("Schwab", "Tax")
    return TestClient(create_app(settings), raise_server_exceptions=False)


def test_overview_drops_portfolio_section_header(seeded_client: TestClient):
    """The Portfolio section-header div below the H1 was duplicate noise and
    is gone (P1). The body fragment should not repeat a 'Portfolio' heading."""
    html = seeded_client.get("/portfolio/body").text
    # The old pattern was a standalone div with text "Portfolio" acting as a
    # section header redundant to the page H1.
    assert '<div class="text-[14px] font-semibold tracking-tightish mb-2 text-label-1">Portfolio</div>' not in html


def test_overview_drops_tax_planning_footer_panel(seeded_client: TestClient):
    """The "Tax planning" footer panel on Overview is gone (P9). Tax-planning
    work belongs on /tax."""
    html = seeded_client.get("/portfolio/body").text
    assert "Tax planning" not in html


def test_overview_renders_cash_kpi_exactly_once(seeded_client: TestClient):
    """The CASH KPI was emitted twice — duplicate-render bug (P3). Counting
    `data-kpi-slot="cash"` is the cleanest assertion."""
    html = seeded_client.get("/portfolio/kpis").text
    cash_count = html.count('data-kpi-slot="cash"')
    assert cash_count == 1, f"CASH KPI rendered {cash_count} times; expected 1"


def test_overview_freshness_chip_lives_in_toolbar(seeded_client: TestClient):
    """One freshness chip in the toolbar — not duplicated across KPI tiles."""
    html = seeded_client.get("/").text
    assert 'data-testid="freshness-chip"' in html


def test_overview_does_not_repeat_cached_prices_phrase(seeded_client: TestClient):
    """The "Cached prices …" copy was repeated in multiple tiles. Now it's
    one chip."""
    html = seeded_client.get("/portfolio/kpis").text
    cached_count = html.lower().count("cached prices")
    assert cached_count <= 1, f"'cached prices' appears {cached_count}× — expected ≤1"
