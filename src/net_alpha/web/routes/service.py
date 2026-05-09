"""/settings/service — health page, log tail, controls."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
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


@router.get("/pill", response_class=HTMLResponse)
async def status_pill(request: Request) -> HTMLResponse:
    s = control.status()
    state = getattr(request.app.state, "service_state", None)
    last_price = state.last_run("price_refresh") if state is not None else None
    last_watch = state.last_run("washsale_watch") if state is not None else None

    paused = bool(state.paused) if state is not None else False
    consecutive = state.consecutive_failures("price_refresh") if state is not None else 0

    if not s.installed:
        css = "pill--unknown"
    elif s.disabled:
        css = "pill--stopped"
    elif paused:
        css = "pill--paused"
    elif last_price and consecutive >= 2:
        css = "pill--stale"
    elif s.running:
        css = "pill--running"
    else:
        css = "pill--unknown"

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "_settings_service_status_pill.html",
        {
            "css": css,
            "last_price": last_price,
            "last_watch": last_watch,
        },
    )


@router.post("/control", response_class=HTMLResponse)
async def control_post(request: Request, action: str = Form(...)):
    state = getattr(request.app.state, "service_state", None)
    sched = getattr(request.app.state, "scheduler", None)

    if action == "pause":
        if state is not None and sched is not None:
            control.pause_in_process(state=state, scheduler=sched)
    elif action == "resume":
        if state is not None and sched is not None:
            control.resume_in_process(state=state, scheduler=sched)
    elif action == "restart":
        try:
            control.restart()
        except (control.NotInstalled, control.ServiceStopped) as e:
            return HTMLResponse(str(e), status_code=409)
    elif action == "stop":
        control.stop(reason="user clicked Stop in UI")
    else:
        return HTMLResponse(f"unknown action: {action}", status_code=400)

    # Return the updated pill so HTMX can swap it in immediately.
    return await status_pill(request)
