# tests/web/test_density_toggle_render.py
from importlib.resources import files

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient

from net_alpha.prefs.profile import ProfileSettings


def test_density_toggle_marks_current(tmp_path):
    templates_dir = files("net_alpha.web") / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))
    app = FastAPI()

    @app.get("/x")
    def _ep(request: Request):
        return templates.TemplateResponse(
            request,
            "_density_toggle.html",
            {
                "profile": ProfileSettings(profile="active", density="tax"),
                "page_key": "/holdings",
                "selected_account": "Schwab/Tax",
                "account_id": 1,
            },
        )

    html = TestClient(app).get("/x").text
    assert 'data-density="tax" aria-current="true"' in html
    assert 'data-density="compact"' in html
    assert 'data-density="comfortable"' in html
    assert 'data-page-key="/holdings"' in html


def test_density_toggle_omits_account_id_when_all(tmp_path):
    templates_dir = files("net_alpha.web") / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))
    app = FastAPI()

    @app.get("/x")
    def _ep(request: Request):
        return templates.TemplateResponse(
            request,
            "_density_toggle.html",
            {
                "profile": ProfileSettings(profile="active", density="comfortable"),
                "page_key": "/holdings",
                "selected_account": "",
                "account_id": None,
            },
        )

    html = TestClient(app).get("/x").text
    assert 'name="account_id"' not in html
