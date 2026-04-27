"""Merged /wash-sales route — combines the old /detail (table) and /calendar
(year ribbon) views under a single URL with ?view=table|calendar toggle.

Filters (ticker, account, year, confidence) apply identically to both views.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from net_alpha.db.repository import Repository
from net_alpha.portfolio.detail_aggregations import (
    compute_detail_summary,
    group_violations_by_ticker,
    lag_days,
    source_label,
)
from net_alpha.web.dependencies import get_repository

router = APIRouter()

EXPAND_THRESHOLD = 5


def _day_of_year_pct(day: _date) -> float:
    start = _date(day.year, 1, 1)
    end = _date(day.year, 12, 31)
    total = (end - start).days
    return ((day - start).days / total) * 100 if total else 0


def _sort_key(sort: str | None):
    if sort == "lag":

        def key(v):
            d = lag_days(v)
            return (d is None, d or 0)

        return key
    return lambda v: v.loss_sale_date or _date.min


@router.get("/wash-sales", response_class=HTMLResponse)
def wash_sales_page(
    request: Request,
    repo: Repository = Depends(get_repository),
    view: str = Query("table"),
    ticker: str | None = Query(None),
    account: str | None = Query(None),
    year: int | None = Query(None),
    confidence: str | None = Query(None),
    sort: str | None = Query(None),
    order: str | None = Query("desc"),
) -> HTMLResponse:
    if view not in ("table", "calendar"):
        view = "table"

    today = _date.today()
    all_v = repo.all_violations()

    violations = list(all_v)
    if ticker:
        violations = [v for v in violations if v.ticker == ticker.upper()]
    if account:
        violations = [v for v in violations if account in (v.loss_account, v.buy_account)]
    if year:
        violations = [v for v in violations if v.loss_sale_date and v.loss_sale_date.year == year]
    if confidence:
        violations = [v for v in violations if v.confidence.lower() == confidence.lower()]

    # Year list spans every year with trade or violation activity, plus the current year.
    year_set = {v.loss_sale_date.year for v in all_v if v.loss_sale_date}
    year_set.update(t.date.year for t in repo.all_trades())
    year_set.add(today.year)
    years = sorted(year_set, reverse=True)
    selected_year = year or today.year

    ctx: dict = {
        "view": view,
        "filter_ticker": ticker or "",
        "filter_account": account or "",
        "filter_year": year or "",
        "filter_confidence": confidence or "",
        "tickers": repo.list_distinct_tickers(),
        "accounts": [a.display() for a in repo.list_accounts()],
        "years": years,
        "selected_year": selected_year,
    }

    if view == "calendar":
        # Calendar additionally needs a per-year filter applied if no `year` was passed.
        cal_violations = (
            violations
            if year is not None
            else [v for v in violations if v.loss_sale_date and v.loss_sale_date.year == selected_year]
        )
        markers = [
            {
                "id": v.id,
                "ticker": v.ticker,
                "date": v.loss_sale_date,
                "left_pct": _day_of_year_pct(v.loss_sale_date),
                "confidence": v.confidence,
                "loss_account": v.loss_account or "-",
                "disallowed": v.disallowed_loss,
            }
            for v in cal_violations
        ]
        ctx.update({"markers": markers, "sort": "", "order": ""})
    else:
        # Table view: sort + group + summary.
        reverse = (order or "desc").lower() != "asc"
        key = _sort_key(sort)
        summary = compute_detail_summary(violations)
        groups = group_violations_by_ticker(violations)
        for g in groups:
            g.violations.sort(key=key, reverse=reverse)
        expand_default = len(groups) <= EXPAND_THRESHOLD
        ctx.update(
            {
                "violations": violations,
                "summary": summary,
                "groups": groups,
                "expand_default": expand_default,
                "lag_days": lag_days,
                "source_label": source_label,
                "sort": sort or "",
                "order": order or "desc",
                "next_lag_order": "asc" if (sort == "lag" and (order or "desc") == "desc") else "desc",
            }
        )

    return request.app.state.templates.TemplateResponse(request, "wash_sales.html", ctx)


# 301 redirects from old paths — preserve query string.


@router.get("/detail")
def detail_redirect(request: Request) -> RedirectResponse:
    qs = request.url.query
    return RedirectResponse(url=f"/wash-sales?{qs}" if qs else "/wash-sales", status_code=301)


@router.get("/calendar")
def calendar_redirect(request: Request) -> RedirectResponse:
    qs = request.url.query
    target = f"/wash-sales?view=calendar&{qs}" if qs else "/wash-sales?view=calendar"
    return RedirectResponse(url=target, status_code=301)


@router.get("/wash-sales/focus/{violation_id}", response_class=HTMLResponse)
def wash_sales_focus(
    violation_id: str,
    request: Request,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    target = next((v for v in repo.all_violations() if v.id == violation_id), None)
    if target is None or not target.loss_sale_date:
        raise HTTPException(status_code=404, detail=f"Violation {violation_id} not found")

    window_start = target.loss_sale_date - timedelta(days=30)
    window_end = target.loss_sale_date + timedelta(days=30)
    related_trades = [t for t in repo.get_trades_for_ticker(target.ticker) if window_start <= t.date <= window_end]

    markers = []
    for t in related_trades:
        offset_days = (t.date - target.loss_sale_date).days
        left_pct = ((offset_days + 30) / 60) * 100
        is_loss_sale = t.date == target.loss_sale_date
        is_triggering = t.date == target.triggering_buy_date
        markers.append(
            {
                "trade": t,
                "left_pct": left_pct,
                "is_loss_sale": is_loss_sale,
                "is_triggering": is_triggering,
                "offset_label": f"day {offset_days:+d}",
            }
        )

    return request.app.state.templates.TemplateResponse(
        request,
        "_calendar_focus.html",
        {
            "violation": target,
            "markers": markers,
            "window_start": window_start,
            "window_end": window_end,
        },
    )
