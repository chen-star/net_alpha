from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.web.dependencies import get_repository

router = APIRouter()


@router.get("/detail", response_class=HTMLResponse)
def detail_page(
    request: Request,
    repo: Repository = Depends(get_repository),
    ticker: str | None = Query(None),
    account: str | None = Query(None),
    year: int | None = Query(None),
    confidence: str | None = Query(None),
) -> HTMLResponse:
    violations = repo.all_violations()
    if ticker:
        violations = [v for v in violations if v.ticker == ticker.upper()]
    if account:
        violations = [v for v in violations if account in (v.loss_account, v.buy_account)]
    if year:
        violations = [v for v in violations if v.loss_sale_date and v.loss_sale_date.year == year]
    if confidence:
        violations = [v for v in violations if v.confidence.lower() == confidence.lower()]

    return request.app.state.templates.TemplateResponse(
        request,
        "detail.html",
        {
            "violations": violations,
            "filter_ticker": ticker or "",
            "filter_account": account or "",
            "filter_year": year or "",
            "filter_confidence": confidence or "",
            "tickers": repo.list_distinct_tickers(),
            "accounts": [a.display() for a in repo.list_accounts()],
        },
    )
