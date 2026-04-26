from __future__ import annotations

from importlib.resources import files

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from net_alpha.config import Settings


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="net-alpha")
    app.state.settings = settings

    static_dir = files("net_alpha.web") / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
