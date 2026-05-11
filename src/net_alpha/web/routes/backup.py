"""Settings → Backup page: list bundles + create-now button. No restore form."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

import net_alpha.backup as backup

router = APIRouter()


@router.get("/settings/backup", response_class=HTMLResponse)
def settings_backup_page(request: Request) -> HTMLResponse:
    bundles = backup.list_bundles()
    return request.app.state.templates.TemplateResponse(
        request,
        "backup.html",
        {"bundles": bundles},
    )


@router.post("/settings/backup/create", response_class=HTMLResponse)
def settings_backup_create(request: Request) -> HTMLResponse:
    backup.create_bundle(reason="manual")
    bundles = backup.list_bundles()
    return request.app.state.templates.TemplateResponse(
        request,
        "_backup_list.html",
        {"bundles": bundles},
    )
