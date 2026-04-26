from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.web.dependencies import get_repository

router = APIRouter()


@router.get("/imports", response_class=HTMLResponse)
def imports_page(request: Request, repo: Repository = Depends(get_repository)) -> HTMLResponse:
    records = repo.list_imports()
    return request.app.state.templates.TemplateResponse(
        request,
        "imports.html",
        {"imports": records},
    )
