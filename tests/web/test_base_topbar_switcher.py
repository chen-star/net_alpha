from datetime import UTC, datetime

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.preferences import AccountPreference
from net_alpha.web.app import create_app


def test_base_topbar_includes_profile_switcher(tmp_path):
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
            updated_at=datetime(2026, 4, 27, tzinfo=UTC),
        )
    )
    app = create_app(settings)
    client = TestClient(app)
    html = client.get("/").text
    # The switcher button label uses the profile name
    assert ">options<" in html.lower() or "options</span>" in html
    # And it includes a per-account form action to /preferences
    assert 'action="/preferences"' in html


def test_base_topbar_omitted_when_no_accounts(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    app = create_app(settings)
    client = TestClient(app)
    html = client.get("/").text
    assert 'action="/preferences"' not in html
