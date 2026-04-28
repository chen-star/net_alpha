from importlib.resources import files

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient

from net_alpha.models.domain import Account
from net_alpha.prefs.profile import ProfileSettings


def test_profile_switcher_lists_each_account_with_profile_dropdown(tmp_path):
    templates_dir = files("net_alpha.web") / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))
    app = FastAPI()

    @app.get("/x")
    def _ep(request: Request):
        return templates.TemplateResponse(
            request,
            "_profile_switcher.html",
            {
                "accounts": [Account(id=1, broker="Schwab", label="Tax"), Account(id=2, broker="Schwab", label="Roth")],
                "account_profiles": {1: "active", 2: "options"},
                "profile": ProfileSettings(profile="active", density="comfortable"),
            },
        )

    client = TestClient(app)
    html = client.get("/x").text
    assert "Schwab/Tax" in html
    assert "Schwab/Roth" in html
    assert 'name="profile"' in html
    assert 'value="conservative"' in html
    assert 'value="active"' in html
    assert 'value="options"' in html


def test_profile_switcher_marks_current_profile(tmp_path):
    templates_dir = files("net_alpha.web") / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))
    app = FastAPI()

    @app.get("/x")
    def _ep(request: Request):
        return templates.TemplateResponse(
            request,
            "_profile_switcher.html",
            {
                "accounts": [Account(id=1, broker="Schwab", label="Tax")],
                "account_profiles": {1: "options"},
                "profile": ProfileSettings(profile="options", density="comfortable"),
            },
        )

    client = TestClient(app)
    html = client.get("/x").text
    # the dropdown for account 1 should preselect "options"
    assert 'value="options" selected' in html
