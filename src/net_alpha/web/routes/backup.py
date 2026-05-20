"""Settings → Backup page: list bundles + create-now button. No restore form."""

from __future__ import annotations

import html

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from loguru import logger

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
    try:
        backup.create_bundle(reason="manual")
    except Exception as e:
        logger.warning("Web-triggered backup failed: {}", e)
        return HTMLResponse(
            f'<div id="backup-list" class="error">Backup failed: {html.escape(str(e))}</div>',
            status_code=500,
        )
    bundles = backup.list_bundles()
    return request.app.state.templates.TemplateResponse(
        request,
        "_backup_list.html",
        {"bundles": bundles},
    )
