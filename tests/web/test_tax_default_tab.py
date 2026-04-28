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
    client = _seed(tmp_path, "active")
    html = client.get("/tax", params={"account": "Schwab/Tax"}).text
    # the harvest tab is "active" in the nav
    assert 'class="tab tab--active"' in html
    assert 'href="/tax?view=harvest&amp;account=Schwab/Tax"' in html or "view=harvest" in html
    # Inner panel renders the harvest queue marker, not the wash-sales table
    assert "Harvest queue" in html


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
