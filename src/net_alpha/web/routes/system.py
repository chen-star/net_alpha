from __future__ import annotations

import html
import os
import signal
import traceback

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, JSONResponse


def _is_hx_request(request: Request) -> bool:
    """True for fragment-swap requests from HTMX.

    Used by the error handlers to return a small inline-styled fragment
    instead of a full ``error.html`` page — otherwise HTMX would swap a
    complete ``<html>`` document into a small fragment target, shattering
    the layout.
    """
    return request.headers.get("hx-request", "").lower() == "true"


def _hx_error_fragment(status: int, detail: str) -> HTMLResponse:
    """Render a compact error fragment that fits anywhere an HTMX swap might land."""
    safe = html.escape(str(detail))
    title = "Server error" if status >= 500 else "Request error"
    body = (
        '<div role="alert" class="panel" '
        'style="background:var(--color-neg-tint); color:var(--color-neg);'
        " padding:0.6rem 0.75rem; border-radius:6px; font-size:12px;"
        ' border:0.5px solid var(--color-neg);">'
        f"<strong>{title} ({status}).</strong> {safe}"
        "</div>"
    )
    return HTMLResponse(body, status_code=status)


router = APIRouter()


@router.post("/quit", response_class=HTMLResponse)
def quit_server() -> HTMLResponse:
    """Send SIGINT to ourselves so uvicorn shuts down cleanly."""
    os.kill(os.getpid(), signal.SIGINT)
    return HTMLResponse("<p>Shutting down…</p>")


@router.get("/__test_500__", include_in_schema=False)
async def _force_500() -> None:
    """Test-only route used to verify the 500 handler renders error.html."""
    raise RuntimeError("forced for tests")


@router.get("/healthz", include_in_schema=False)
async def healthz(request: Request) -> JSONResponse:
    """Liveness+readiness probe for container HEALTHCHECK / deploy gating.

    Returns 200 only if the canonical DB opens and answers SELECT 1, so a
    fundamentally broken release fails the healthcheck and gets rolled back.
    """
    from sqlalchemy import text

    from net_alpha.db.connection import get_engine

    try:
        engine = get_engine(request.app.state.settings.db_path)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "unhealthy"}, status_code=503)
    return JSONResponse({"status": "ok"})


@router.api_route(
    "/{path_name:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    include_in_schema=False,
)
async def catch_all_404(request: Request, path_name: str) -> HTMLResponse:
    """Catch-all route for 404s. Must be registered last."""
    return request.app.state.templates.TemplateResponse(
        request,
        "error.html",
        {"status": 404, "title": "Not found", "detail": f"The page /{path_name} was not found.", "traceback": None},
        status_code=404,
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> HTMLResponse:
        if _is_hx_request(request):
            return _hx_error_fragment(exc.status_code, str(exc.detail))
        if exc.status_code == 404:
            return request.app.state.templates.TemplateResponse(
                request,
                "error.html",
                {"status": 404, "title": "Not found", "detail": str(exc.detail), "traceback": None},
                status_code=404,
            )
        return request.app.state.templates.TemplateResponse(
            request,
            "error.html",
            {"status": exc.status_code, "title": "Error", "detail": str(exc.detail), "traceback": None},
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> HTMLResponse:
        if _is_hx_request(request):
            return _hx_error_fragment(500, str(exc))
        return request.app.state.templates.TemplateResponse(
            request,
            "error.html",
            {"status": 500, "title": "Server error", "detail": str(exc), "traceback": traceback.format_exc()},
            status_code=500,
        )
