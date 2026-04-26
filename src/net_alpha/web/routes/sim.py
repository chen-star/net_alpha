from __future__ import annotations

from datetime import date as _date
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.engine.etf_pairs import load_etf_pairs
from net_alpha.engine.simulator import simulate_buy, simulate_sell
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
            "today_iso": _date.today().isoformat(),
            "result": None,
        },
    )


@router.post("/sim", response_class=HTMLResponse)
def sim_run(
    request: Request,
    repo: Repository = Depends(get_repository),
    action: str = Form("sell"),
    ticker: str = Form(...),
    qty: float = Form(...),
    price: float = Form(...),
    account: str = Form(""),
    trade_date: str = Form(""),
) -> HTMLResponse:
    on_date = _date.fromisoformat(trade_date) if trade_date else _date.today()
    accounts = repo.list_accounts()
    accounts_filtered = [a for a in accounts if a.display() == account] if account else accounts

    if action.lower() == "buy":
        options = simulate_buy(
            ticker=ticker.upper(),
            qty=Decimal(str(qty)),
            price=Decimal(str(price)),
            account=account or None,
            on_date=on_date,
            accounts=accounts,
            recent_trades=repo.all_trades(),
            existing_violations=repo.all_violations(),
            etf_pairs=load_etf_pairs(),
        )
        return request.app.state.templates.TemplateResponse(
            request,
            "_sim_buy_result.html",
            {"options": options, "ticker": ticker.upper()},
        )

    options = simulate_sell(
        ticker=ticker.upper(),
        qty=Decimal(str(qty)),
        price=Decimal(str(price)),
        accounts=accounts_filtered,
        existing_lots=repo.all_lots(),
        recent_trades=repo.all_trades(),
        today=on_date,
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "_sim_sell_result.html",
        {"options": options, "ticker": ticker.upper()},
    )
