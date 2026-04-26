from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.web.dependencies import get_repository

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, repo: Repository = Depends(get_repository)) -> HTMLResponse:
    imports = repo.list_imports()
    violations = repo.all_violations()
    today = date.today()

    open_violations = [v for v in violations if v.loss_sale_date and (today - v.loss_sale_date).days <= 30]
    ytd_disallowed = sum(
        (v.disallowed_loss for v in violations if v.loss_sale_date and v.loss_sale_date.year == today.year),
        start=0.0,
    )
    ytd_count = sum(1 for v in violations if v.loss_sale_date and v.loss_sale_date.year == today.year)
    return request.app.state.templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "imports": imports,
            "open_violations": open_violations,
            "all_violations": violations,
            "ytd_disallowed": ytd_disallowed,
            "ytd_count": ytd_count,
            "current_year": today.year,
        },
    )
