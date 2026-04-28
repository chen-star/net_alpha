from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.web.app import create_app


def _bootstrap(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)
    repo.get_or_create_account("Schwab", "Tax")
    return settings, repo


def test_post_preferences_creates_row(tmp_path):
    from fastapi.testclient import TestClient

    settings, repo = _bootstrap(tmp_path)
    app = create_app(settings)
    client = TestClient(app)

    aid = repo.list_accounts()[0].id
    resp = client.post(
        "/preferences",
        data={"account_id": str(aid), "profile": "options", "density": "tax"},
    )
    assert resp.status_code == 204
    assert resp.headers.get("hx-refresh") == "true"

    pref = repo.get_user_preference(aid)
    assert pref.profile == "options"
    assert pref.density == "tax"


def test_post_preferences_rejects_invalid_profile(tmp_path):
    from fastapi.testclient import TestClient

    settings, repo = _bootstrap(tmp_path)
    app = create_app(settings)
    client = TestClient(app)

    aid = repo.list_accounts()[0].id
    resp = client.post(
        "/preferences",
        data={"account_id": str(aid), "profile": "bogus", "density": "comfortable"},
    )
    assert resp.status_code == 422


def test_post_preferences_rejects_unknown_account(tmp_path):
    from fastapi.testclient import TestClient

    settings, _ = _bootstrap(tmp_path)
    app = create_app(settings)
    client = TestClient(app)

    resp = client.post(
        "/preferences",
        data={"account_id": "99999", "profile": "active", "density": "comfortable"},
    )
    assert resp.status_code == 404


def test_post_preferences_all_accounts(tmp_path):
    """When no account_id given, write the same prefs to every account."""
    from fastapi.testclient import TestClient

    settings, repo = _bootstrap(tmp_path)
    repo.get_or_create_account("Schwab", "Roth")
    app = create_app(settings)
    client = TestClient(app)

    resp = client.post(
        "/preferences",
        data={"profile": "conservative", "density": "comfortable"},
    )
    assert resp.status_code == 204
    for a in repo.list_accounts():
        pref = repo.get_user_preference(a.id)
        assert pref.profile == "conservative"
