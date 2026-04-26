from __future__ import annotations

from datetime import date as _date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.portfolio.detail_aggregations import (
    compute_detail_summary,
    group_violations_by_ticker,
    lag_days,
    source_label,
)
from net_alpha.web.dependencies import get_repository

router = APIRouter()

EXPAND_THRESHOLD = 5  # default expand state for group-by-ticker


def _sort_key(sort: str | None):
    if sort == "lag":
        return lambda v: (lag_days(v) is None, lag_days(v) or 0)
    return lambda v: v.loss_sale_date or _date.min


@router.get("/detail", response_class=HTMLResponse)
def detail_page(
    request: Request,
    repo: Repository = Depends(get_repository),
    ticker: str | None = Query(None),
    account: str | None = Query(None),
    year: int | None = Query(None),
    confidence: str | None = Query(None),
    sort: str | None = Query(None),  # "lag" supported; default = loss_sale_date desc
    order: str | None = Query("desc"),
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

    reverse = (order or "desc").lower() != "asc"
    key = _sort_key(sort)
    violations.sort(key=key, reverse=reverse)

    summary = compute_detail_summary(violations)
    groups = group_violations_by_ticker(violations)

    # Sort each group's violations using the same key
    for g in groups:
        g.violations.sort(key=key, reverse=reverse)

    expand_default = len(groups) <= EXPAND_THRESHOLD

    return request.app.state.templates.TemplateResponse(
        request,
        "detail.html",
        {
            "violations": violations,
            "summary": summary,
            "groups": groups,
            "expand_default": expand_default,
            "lag_days": lag_days,
            "source_label": source_label,
            "filter_ticker": ticker or "",
            "filter_account": account or "",
            "filter_year": year or "",
            "filter_confidence": confidence or "",
            "sort": sort or "",
            "order": order or "desc",
            "next_lag_order": "asc" if (sort == "lag" and (order or "desc") == "desc") else "desc",
            "tickers": repo.list_distinct_tickers(),
            "accounts": [a.display() for a in repo.list_accounts()],
        },
    )
