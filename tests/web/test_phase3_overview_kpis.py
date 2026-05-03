"""Phase 3 Overview clutter removal + KPI restructure (§4.1, §6.2 P1/P3/P5/P9).

The Overview body is lazy-loaded by HTMX from /portfolio/body. Tests that
assert body-level content (KPIs, charts, panels) use that fragment endpoint.
Tests that assert toolbar-level content hit / directly, since the toolbar
is rendered eagerly in portfolio.html (only when imports exist, so we seed).
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
def seeded_client(tmp_path):
    """Client with one import so the toolbar + body both render.

    The import is necessary because portfolio.html gates the toolbar on
    `{% if imports %}` — without it, the freshness chip never renders.
    """
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


def test_overview_hero_kpi_is_total_account_value(seeded_client):
    """Hero = Total Account Value (P4)."""
    resp = seeded_client.get("/portfolio/kpis")
    html = resp.text
    assert 'data-kpi-slot="hero"' in html
    assert "TOTAL ACCOUNT VALUE" in html or "Total account value" in html


def test_overview_has_total_return_tile(seeded_client):
    """The Total Return tile appears in the top-row of the KPI grid (promoted
    from bottom row, renamed from Growth; TODAY tile dropped)."""
    resp = seeded_client.get("/portfolio/kpis")
    assert 'data-kpi-slot="total_return"' in resp.text
    assert 'data-kpi-slot="today"' not in resp.text


def test_overview_kpi_grid_is_hero_plus_promoted_plus_three_small(seeded_client):
    """Top row: hero (col-span-8) + total_return (col-span-4).
    Bottom row: realized + unrealized + cash (col-span-4 each)."""
    resp = seeded_client.get("/portfolio/kpis")
    html = resp.text
    slots = (
        ("hero", 1),
        ("total_return", 1),
        ("realized", 1),
        ("unrealized", 1),
        ("cash", 1),
    )
    for slot, expected in slots:
        actual = html.count(f'data-kpi-slot="{slot}"')
        assert actual == expected, f"slot={slot} appears {actual}× (expected {expected})"
    # Removed slots must not appear (today/growth dropped earlier; contributed
    # folded into the Cash subtitle).
    for removed in ("today", "growth", "contributed"):
        assert f'data-kpi-slot="{removed}"' not in html, f"removed slot={removed} still present"


def test_cash_kpi_tile_includes_net_contributed_subtitle(seeded_client):
    """Net Contributed is no longer its own tile — it lives as a subtitle on
    the Cash tile so users still see the figure but the KPI grid hierarchy
    isn't diluted by an operational-only metric."""
    html = seeded_client.get("/portfolio/kpis").text
    # Locate the Cash tile span and assert the subtitle copy.
    assert 'data-kpi-slot="cash"' in html
    assert "contributed" in html.lower()  # subtitle text on the Cash tile


def test_fmt_currency_prepends_minus_for_negatives():
    """Today tile shows ``-$50.00`` (with leading minus), not ``$50.00``,
    when the day's net change is negative (review C1 regression)."""
    from decimal import Decimal

    from net_alpha.web.format import fmt_currency

    # Sanity: fmt_currency emits the minus sign.
    result = fmt_currency(Decimal("-50.00"))
    assert result.startswith("-") or result.startswith("−"), (
        f"fmt_currency does not prepend a minus for negatives: {result!r}"
    )


def test_app_css_defines_text_loss_text_gain_text_success():
    """The .text-loss / .text-gain / .text-success classes are used by
    multiple templates and must produce visible color (review C2)."""
    from pathlib import Path

    css_path = Path(__file__).parent.parent.parent / "src" / "net_alpha" / "web" / "static" / "app.css"
    css = css_path.read_text()
    for cls in (".text-loss", ".text-gain", ".text-success"):
        assert cls in css, f"{cls} missing from app.css — templates using it render uncolored"
