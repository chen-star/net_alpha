from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.web.dependencies import get_repository

router = APIRouter()


@router.get("/holdings", response_class=HTMLResponse)
def holdings_page(
    request: Request,
    period: str | None = None,
    account: str | None = None,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    imports = repo.list_imports()
    accounts = sorted({imp.account_display for imp in imports})

    today = date.today()
    current_year = today.year
    import_years = {imp.imported_at.year for imp in imports}
    available_years = sorted(import_years | {current_year}, reverse=True)

    selected_period = period or "ytd"
    return request.app.state.templates.TemplateResponse(
        request,
        "holdings.html",
        {
            "imports": imports,
            "accounts": accounts,
            "available_years": available_years,
            "current_year": current_year,
            "selected_period": selected_period,
            "selected_account": account or "",
            "group_options": "merge",
            "toolbar_action": "/holdings",
        },
    )
