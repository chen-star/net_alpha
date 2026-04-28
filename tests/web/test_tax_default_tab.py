"""Task 22: /tax default tab follows ProfileSettings.default_tax_tab()."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.preferences import AccountPreference
from net_alpha.web.app import create_app


def _seed(tmp_path, profile_label):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)
    a = repo.get_or_create_account("Schwab", "Tax")
    repo.upsert_user_preference(
        AccountPreference(
            account_id=a.id,
            profile=profile_label,
            density="comfortable",
            updated_at=datetime(2026, 4, 27, tzinfo=UTC),
        )
    )
    app = create_app(settings)
    return TestClient(app)


def test_tax_no_view_active_renders_harvest(tmp_path):
    """Phase 1 IA: Harvest tab is removed from /tax nav. The active profile still
    routes to harvest content internally (data-active-tab="harvest") and renders
    the harvest queue in the content area. The nav tab link is gone — harvest has
    moved to /positions?view=at-loss."""
    client = _seed(tmp_path, "active")
    html = client.get("/tax", params={"account": "Schwab/Tax"}).text
    # Phase 1: the Harvest tab link is removed from the nav (moved to /positions).
    assert 'href="/tax?view=harvest' not in html
    # The route still resolves the active profile's default (harvest) and renders
    # the harvest content in the content area.
    assert "Harvest queue" in html
    # The wrapper div still carries the active-tab marker for JS continuity.
    assert 'data-active-tab="harvest"' in html


def test_tax_no_view_conservative_renders_wash_sales(tmp_path):
    client = _seed(tmp_path, "conservative")
    html = client.get("/tax", params={"account": "Schwab/Tax"}).text
    assert "Wash sales" in html
    # The active tab is wash-sales, harvest is not preselected
    # (assert by URL query absence of view=harvest in active tab is brittle —
    # use a positive marker instead)
    assert 'data-active-tab="wash-sales"' in html


def test_tax_explicit_view_overrides_profile(tmp_path):
    client = _seed(tmp_path, "active")
    html = client.get("/tax", params={"view": "wash-sales"}).text
    assert 'data-active-tab="wash-sales"' in html
