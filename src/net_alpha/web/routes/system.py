from __future__ import annotations

import os
import signal
import traceback

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse

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


@router.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"], include_in_schema=False)
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
        if exc.status_code == 404:
            return request.app.state.templates.TemplateResponse(
                request,
                "error.html",
                {"status": 404, "title": "Not found", "detail": str(exc.detail), "traceback": None},
                status_code=404,
            )
        else:
            return request.app.state.templates.TemplateResponse(
                request,
                "error.html",
                {"status": exc.status_code, "title": "Error", "detail": str(exc.detail), "traceback": None},
                status_code=exc.status_code,
            )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> HTMLResponse:
        return request.app.state.templates.TemplateResponse(
            request,
            "error.html",
            {"status": 500, "title": "Server error", "detail": str(exc), "traceback": traceback.format_exc()},
            status_code=500,
        )
