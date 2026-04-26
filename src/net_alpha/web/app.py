from __future__ import annotations

from fastapi import FastAPI

from net_alpha.config import Settings


def create_app(settings: Settings) -> FastAPI:
    """Build the FastAPI app for the local UI.

    The settings parameter lets tests override the DB location; production
    callers pass Settings() to use the default ~/.net_alpha/ path.
    """
    app = FastAPI(title="net-alpha")
    app.state.settings = settings

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
