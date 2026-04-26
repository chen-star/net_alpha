from __future__ import annotations

from importlib.resources import files

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from net_alpha.config import Settings
from net_alpha.engine.etf_pairs import load_etf_pairs
from net_alpha.output.disclaimer import render as disclaimer_render


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="net-alpha")
    app.state.settings = settings
    app.state.etf_pairs = load_etf_pairs(user_path=str(settings.user_etf_pairs_path))

    static_dir = files("net_alpha.web") / "static"
    templates_dir = files("net_alpha.web") / "templates"

    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    templates = Jinja2Templates(directory=str(templates_dir))
    templates.env.globals["disclaimer"] = disclaimer_render()
    app.state.templates = templates

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def root_placeholder(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "base.html", {})

    return app
