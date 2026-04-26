from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.engine.simulator import simulate_sell
from net_alpha.web.dependencies import get_repository

router = APIRouter()


@router.get("/sim", response_class=HTMLResponse)
def sim_form(
    request: Request,
    repo: Repository = Depends(get_repository),
    ticker: str | None = None,
) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        request,
        "sim.html",
        {
            "ticker": ticker or "",
            "tickers": repo.list_distinct_tickers(),
            "accounts": [a.display() for a in repo.list_accounts()],
            "result": None,
        },
    )


@router.post("/sim", response_class=HTMLResponse)
def sim_run(
    request: Request,
    repo: Repository = Depends(get_repository),
    ticker: str = Form(...),
    qty: float = Form(...),
    price: float = Form(...),
    account: str = Form(""),
) -> HTMLResponse:
    accounts = repo.list_accounts()
    if account:
        accounts = [a for a in accounts if a.display() == account]

    options = simulate_sell(
        ticker=ticker.upper(),
        qty=Decimal(str(qty)),
        price=Decimal(str(price)),
        accounts=accounts,
        existing_lots=repo.all_lots(),
        recent_trades=repo.all_trades(),
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "_sim_result.html",
        {"options": options, "ticker": ticker.upper()},
    )
