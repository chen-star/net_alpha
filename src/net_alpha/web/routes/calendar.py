from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.web.dependencies import get_repository

router = APIRouter()


def _day_of_year_pct(day: date) -> float:
    """Return percentage (0-100) of a day's position within its calendar year."""
    start = date(day.year, 1, 1)
    end = date(day.year, 12, 31)
    total = (end - start).days
    return ((day - start).days / total) * 100 if total else 0


@router.get("/calendar", response_class=HTMLResponse)
def calendar_page(
    request: Request,
    repo: Repository = Depends(get_repository),
    year: int | None = Query(None),
    ticker: str | None = Query(None),
    account: str | None = Query(None),
    confidence: str | None = Query(None),
) -> HTMLResponse:
    today = date.today()
    selected_year = year or today.year
    all_v = repo.all_violations()
    violations = [v for v in all_v if v.loss_sale_date and v.loss_sale_date.year == selected_year]
    if ticker:
        violations = [v for v in violations if v.ticker == ticker.upper()]
    if account:
        violations = [v for v in violations if account in (v.loss_account, v.buy_account)]
    if confidence:
        violations = [v for v in violations if v.confidence.lower() == confidence.lower()]

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
        for v in violations
    ]
    years = sorted({v.loss_sale_date.year for v in all_v if v.loss_sale_date}) or [today.year]
    return request.app.state.templates.TemplateResponse(
        request,
        "calendar.html",
        {
            "markers": markers,
            "selected_year": selected_year,
            "years": years,
            "filter_ticker": ticker or "",
            "filter_account": account or "",
            "filter_confidence": confidence or "",
            "tickers": repo.list_distinct_tickers(),
            "accounts": [a.display() for a in repo.list_accounts()],
        },
    )


@router.get("/calendar/focus/{violation_id}", response_class=HTMLResponse)
def calendar_focus(
    violation_id: str,
    request: Request,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    target = next((v for v in repo.all_violations() if v.id == violation_id), None)
    if target is None or not target.loss_sale_date:
        raise HTTPException(status_code=404, detail=f"Violation {violation_id} not found")

    window_start = target.loss_sale_date - timedelta(days=30)
    window_end = target.loss_sale_date + timedelta(days=30)
    related_trades = [
        t for t in repo.get_trades_for_ticker(target.ticker)
        if window_start <= t.date <= window_end
    ]

    markers = []
    for t in related_trades:
        offset_days = (t.date - target.loss_sale_date).days
        left_pct = ((offset_days + 30) / 60) * 100
        is_loss_sale = t.date == target.loss_sale_date
        is_triggering = t.date == target.triggering_buy_date
        markers.append({
            "trade": t,
            "left_pct": left_pct,
            "is_loss_sale": is_loss_sale,
            "is_triggering": is_triggering,
            "offset_label": f"day {offset_days:+d}",
        })

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
