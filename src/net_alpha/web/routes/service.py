"""/settings/service — health page, log tail, controls."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from net_alpha.db.repository import Repository
from net_alpha.service import control
from net_alpha.web.dependencies import get_repository

router = APIRouter(prefix="/settings/service")


@router.get("", response_class=HTMLResponse)
async def settings_service(
    request: Request,
    err: str | None = None,
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
            "err": err,
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


@router.post("/control")
async def control_post(request: Request, action: str = Form(...)) -> Response:
    """Run a lifecycle action and redirect back to the service page.

    Errors surface inline on the page via the `err` query string. HTMX
    callers (e.g. a future inline-pill button) get the updated pill back
    so they can swap it in place without a full reload.
    """
    state = getattr(request.app.state, "service_state", None)
    sched = getattr(request.app.state, "scheduler", None)
    err: str | None = None

    try:
        if action == "install":
            control.install(port=18765)
        elif action == "uninstall":
            control.uninstall()
        elif action == "start":
            control.start()
        elif action == "stop":
            control.stop(reason="user clicked Stop in UI")
        elif action == "restart":
            control.restart()
        elif action == "pause":
            if state is None or sched is None:
                err = "Scheduler is not running in this process."
            else:
                control.pause_in_process(state=state, scheduler=sched)
        elif action == "resume":
            if state is None or sched is None:
                err = "Scheduler is not running in this process."
            else:
                control.resume_in_process(state=state, scheduler=sched)
        else:
            err = f"unknown action: {action}"
    except (control.NotInstalled, control.ServiceStopped, control.MissingUv) as e:
        err = str(e)
    except Exception as e:  # noqa: BLE001 — surface unexpected failures to the user
        err = f"{type(e).__name__}: {e}"

    if request.headers.get("hx-request") == "true":
        if err:
            return HTMLResponse(err, status_code=409)
        return await status_pill(request)

    target = "/settings/service"
    if err:
        target = f"{target}?err={quote(err)}"
    return RedirectResponse(target, status_code=303)
