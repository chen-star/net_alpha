"""Splash route and start handlers for the onboarding tour."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine
from net_alpha.db.repository import Repository
from net_alpha.web.demo import ensure_demo_db

router = APIRouter()


def _has_real_imports(request: Request) -> bool:
    settings: Settings = request.app.state.settings
    repo = Repository(get_engine(settings.db_path))
    return len(repo.list_imports()) > 0


@router.get("/welcome")
def welcome(request: Request) -> Response:
    if _has_real_imports(request) and "replay" not in request.query_params:
        return RedirectResponse("/", status_code=303)
    from net_alpha.service import control as _ctrl

    _s = _ctrl.status()
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(request, "welcome.html", {"service_installed": _s.installed})


@router.post("/welcome/start-tour")
def start_tour(request: Request) -> RedirectResponse:
    settings: Settings = request.app.state.settings
    ensure_demo_db(settings.data_dir / "demo.db")
    request.app.state.demo_mode = True
    return RedirectResponse("/?tour=1", status_code=303)


@router.post("/welcome/install-service")
def install_service_post(request: Request) -> Response:
    from net_alpha.service import control

    try:
        control.install(port=8765)
    except Exception as e:
        return HTMLResponse(f"<p>Install failed: {e}</p>", status_code=500)
    return RedirectResponse("/", status_code=303)


@router.post("/welcome/start-import")
def start_import(request: Request) -> RedirectResponse:
    return RedirectResponse("/imports", status_code=303)
