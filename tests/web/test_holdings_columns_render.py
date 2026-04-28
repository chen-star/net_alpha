# tests/web/test_holdings_columns_render.py
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.preferences import AccountPreference
from net_alpha.web.app import create_app


def _seed(tmp_path, profile_label, density="comfortable"):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)
    a = repo.get_or_create_account("Schwab", "Tax")
    repo.upsert_user_preference(
        AccountPreference(
            account_id=a.id,
            profile=profile_label,
            density=density,
            updated_at=datetime(2026, 4, 27, tzinfo=UTC),
        )
    )
    app = create_app(settings)
    return TestClient(app)


def test_holdings_conservative_no_extra_columns(tmp_path):
    client = _seed(tmp_path, "conservative")
    # The _portfolio_table.html fragment is rendered by /portfolio/positions
    html = client.get(
        "/portfolio/positions",
        params={"account": "Schwab/Tax", "period": "ytd", "show": "open", "page": "1"},
    ).text
    assert 'data-col="days_held"' not in html
    assert 'data-col="lt_st_split"' not in html


def test_holdings_active_has_days_held_and_lt_st(tmp_path):
    client = _seed(tmp_path, "active")
    html = client.get(
        "/portfolio/positions",
        params={"account": "Schwab/Tax", "period": "ytd", "show": "open", "page": "1"},
    ).text
    assert 'data-col="days_held"' in html
    assert 'data-col="lt_st_split"' in html


def test_holdings_options_has_premium_received(tmp_path):
    client = _seed(tmp_path, "options")
    html = client.get(
        "/portfolio/positions",
        params={"account": "Schwab/Tax", "period": "ytd", "show": "open", "page": "1"},
    ).text
    assert 'data-col="premium_received"' in html


def test_holdings_compact_strips_all_extras(tmp_path):
    client = _seed(tmp_path, "options", density="compact")
    html = client.get(
        "/portfolio/positions",
        params={"account": "Schwab/Tax", "period": "ytd", "show": "open", "page": "1"},
    ).text
    assert 'data-col="premium_received"' not in html
    assert 'data-col="days_held"' not in html
