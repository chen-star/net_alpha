"""/settings/accounts — let the user classify each account label."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.models.accounts import AccountType
from net_alpha.web.dependencies import get_repository

router = APIRouter(prefix="/settings/accounts")

VALID_TYPES = {t.value for t in AccountType}


@router.get("", response_class=HTMLResponse)
async def list_accounts(request: Request, repo: Repository = Depends(get_repository)) -> HTMLResponse:
    rows = repo.list_accounts()
    return request.app.state.templates.TemplateResponse(
        request,
        "_settings_accounts.html",
        {
            "accounts": rows,
            "types": [t.value for t in AccountType],
        },
    )


@router.post("", response_class=HTMLResponse)
async def update_account(
    request: Request,
    broker: str = Form(...),
    label: str = Form(...),
    type: str = Form(...),
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    if type not in VALID_TYPES:
        return HTMLResponse(f"invalid type: {type}", status_code=400)
    repo.set_account_type(broker=broker, label=label, type_=type)
    return await list_accounts(request, repo=repo)
