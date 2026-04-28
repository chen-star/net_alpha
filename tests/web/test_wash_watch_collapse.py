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


def test_wash_watch_open_for_active(tmp_path):
    client = _seed(tmp_path, "active")
    html = client.get("/portfolio/body", params={"account": "Schwab/Tax"}).text
    # <details ... open> when active
    assert "<details open" in html


def test_wash_watch_collapsed_for_conservative_when_no_violation(tmp_path):
    client = _seed(tmp_path, "conservative")
    html = client.get("/portfolio/body", params={"account": "Schwab/Tax"}).text
    # <details> without "open" attribute
    assert "<details>" in html or "<details \n" in html
    assert "<details open" not in html
