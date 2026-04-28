from datetime import UTC, datetime

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.preferences import AccountPreference
from net_alpha.web.app import create_app


def test_modal_shows_when_no_prefs_rows_and_accounts_exist(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)
    repo.get_or_create_account("Schwab", "Tax")
    app = create_app(settings)
    client = TestClient(app)
    html = client.get("/").text
    assert "Pick a default profile per account" in html


def test_modal_hidden_when_any_pref_exists(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)
    a = repo.get_or_create_account("Schwab", "Tax")
    repo.upsert_user_preference(
        AccountPreference(
            account_id=a.id,
            profile="active",
            density="comfortable",
            updated_at=datetime(2026, 4, 27, tzinfo=UTC),
        )
    )
    app = create_app(settings)
    client = TestClient(app)
    html = client.get("/").text
    assert "Pick a default profile per account" not in html


def test_modal_hidden_when_no_accounts_at_all(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    app = create_app(settings)
    client = TestClient(app)
    html = client.get("/").text
    assert "Pick a default profile per account" not in html
