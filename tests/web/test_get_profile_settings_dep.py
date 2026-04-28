# tests/web/test_get_profile_settings_dep.py
import datetime

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlmodel import SQLModel

from net_alpha.config import Settings
from net_alpha.db.repository import Repository
from net_alpha.models.preferences import AccountPreference
from net_alpha.prefs.profile import ProfileSettings
from net_alpha.web.dependencies import get_profile_settings


def _bootstrap_app(tmp_path) -> tuple[FastAPI, Repository]:
    settings = Settings(data_dir=tmp_path)
    engine = create_engine(f"sqlite:///{settings.db_path}")
    SQLModel.metadata.create_all(engine)
    app = FastAPI()
    app.state.settings = settings
    repo = Repository(engine)

    @app.get("/test")
    def _ep(profile: ProfileSettings = Depends(get_profile_settings)) -> dict:
        return {"profile": profile.profile, "density": profile.density}

    return app, repo


def test_get_profile_settings_no_filter_no_prefs(tmp_path):
    app, _repo = _bootstrap_app(tmp_path)
    client = TestClient(app)
    resp = client.get("/test")
    assert resp.status_code == 200
    assert resp.json() == {"profile": "active", "density": "comfortable"}


def test_get_profile_settings_account_filter(tmp_path):
    app, repo = _bootstrap_app(tmp_path)
    acct = repo.get_or_create_account("Schwab", "Tax")
    repo.upsert_user_preference(
        AccountPreference(
            account_id=acct.id,
            profile="options",
            density="tax",
            updated_at=datetime.datetime(2026, 4, 27, tzinfo=datetime.UTC),
        )
    )
    client = TestClient(app)
    resp = client.get("/test", params={"account": "Schwab/Tax"})
    assert resp.status_code == 200
    assert resp.json() == {"profile": "options", "density": "tax"}
