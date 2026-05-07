"""Splash route and start handlers for the onboarding tour."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine
from net_alpha.db.repository import Repository
from net_alpha.web.demo import build_demo_db

router = APIRouter()


def _has_real_imports(request: Request) -> bool:
    settings: Settings = request.app.state.settings
    repo = Repository(get_engine(settings.db_path))
    return len(repo.list_imports()) > 0


@router.get("/welcome")
def welcome(request: Request) -> Response:
    if _has_real_imports(request) and "replay" not in request.query_params:
        return RedirectResponse("/", status_code=303)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(request, "welcome.html", {})


@router.post("/welcome/start-tour")
def start_tour(request: Request) -> RedirectResponse:
    settings: Settings = request.app.state.settings
    demo_path = settings.data_dir / "demo.db"
    if not demo_path.exists():
        build_demo_db(demo_path)
    request.app.state.demo_mode = True
    return RedirectResponse("/?tour=1", status_code=303)


@router.post("/welcome/start-import")
def start_import(request: Request) -> RedirectResponse:
    return RedirectResponse("/imports", status_code=303)
