"""/settings/service — health page, log tail, controls."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.service import control
from net_alpha.web.dependencies import get_repository

router = APIRouter(prefix="/settings/service")


@router.get("", response_class=HTMLResponse)
async def settings_service(
    request: Request,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    s = control.status()
    state = getattr(request.app.state, "service_state", None)
    recent = list(state.recent_runs) if state is not None else []
    return request.app.state.templates.TemplateResponse(
        request,
        "_settings_service.html",
        {
            "status": s,
            "state": state,
            "recent": recent,
        },
    )


@router.get("/runs", response_class=HTMLResponse)
async def settings_service_runs(
    request: Request,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    rows = repo.list_service_runs(limit=50)
    return request.app.state.templates.TemplateResponse(
        request,
        "_settings_service_runs.html",
        {"rows": rows},
    )
