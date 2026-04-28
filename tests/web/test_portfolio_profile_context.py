from datetime import datetime, timezone

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.preferences import AccountPreference
from net_alpha.web.app import create_app


def test_portfolio_kpis_passes_profile_into_template(tmp_path):
    """profile.profile should appear as a class on the KPI hero container."""
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)
    a = repo.get_or_create_account("Schwab", "Tax")
    repo.upsert_user_preference(
        AccountPreference(
            account_id=a.id,
            profile="options",
            density="comfortable",
            updated_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
        )
    )
    app = create_app(settings)
    client = TestClient(app)
    html = client.get("/portfolio/kpis", params={"account": "Schwab/Tax"}).text
    # Marker so we can assert profile reached the KPI fragment.
    assert 'data-profile="options"' in html
