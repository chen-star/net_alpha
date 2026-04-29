"""Merged /wash-sales route — combines the old /detail (table) and /calendar
(year ribbon) views under a single URL with ?view=table|calendar toggle.

Filters (ticker, account, year, confidence) apply identically to both views.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from net_alpha.db.repository import Repository
from net_alpha.portfolio.detail_aggregations import (
    compute_detail_summary,
    group_violations_by_ticker,
    lag_days,
    source_label,
)
from net_alpha.portfolio.tax_planner import compute_offset_budget
from net_alpha.portfolio.wash_watch import recent_loss_closes
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


def _wash_sales_context(
    repo: Repository,
    ticker: str | None = None,
    account: str | None = None,
    year: int | None = None,
    confidence: str | None = None,
    sort: str | None = None,
    order: str = "desc",
    view: str = "table",
) -> dict:
    """Build the wash-sales view context (filters, summary, violations, tickers, accounts...).

    Reusable from the new /tax route. Does NOT include ``request`` or ``active_page`` keys —
    the caller adds those.
    """
    if view not in ("table", "calendar"):
        view = "table"

    today = _date.today()
    all_v = repo.all_violations()

    # Year filter UX: default to current year on first load.
    # Sentinel year=0 means "All years" (explicit user override).
    if year is None:
        effective_year = today.year
    elif year == 0:
        effective_year = None
    else:
        effective_year = year

    violations = list(all_v)
    if ticker:
        violations = [v for v in violations if v.ticker == ticker.upper()]
    if account:
        violations = [v for v in violations if account in (v.loss_account, v.buy_account)]
    if effective_year is not None:
        violations = [v for v in violations if v.loss_sale_date and v.loss_sale_date.year == effective_year]
    if confidence:
        violations = [v for v in violations if v.confidence.lower() == confidence.lower()]

    # Year list spans every year with trade or violation activity, plus the current year.
    year_set = {v.loss_sale_date.year for v in all_v if v.loss_sale_date}
    year_set.update(t.date.year for t in repo.all_trades())
    year_set.add(today.year)
    years = sorted(year_set, reverse=True)
    selected_year = effective_year or today.year

    # Wash-sale watch lives on this tab now (was on Portfolio). Scope by the
    # account filter so the rows match the rest of the page.
    wash_watch_window = 30
    wash_watch_rows = recent_loss_closes(
        repo=repo,
        today=today,
        window_days=wash_watch_window,
        account=account or None,
    )

    ctx: dict = {
        "view": view,
        "filter_ticker": ticker or "",
        "filter_account": account or "",
        # filter_year reflects what's pre-filled in the input. None / 0 => effective default.
        "filter_year": effective_year if effective_year is not None else "",
        "all_years": effective_year is None,
        "filter_confidence": confidence or "",
        "tickers": repo.list_distinct_tickers(),
        "accounts": [a.display() for a in repo.list_accounts()],
        "years": years,
        "selected_year": selected_year,
        # _portfolio_wash_watch.html reads `rows` and `window_days`.
        "rows": wash_watch_rows,
        "window_days": wash_watch_window,
        # T5: realized P/L kpis for the stacked mini-bar.
        "realized_kpis": compute_offset_budget(repo=repo, year=selected_year),
    }

    if view == "calendar":
        # Calendar already filters by selected_year by the time we get here
        # (effective_year was applied above), so just pass violations through.
        cal_violations = (
            violations
            if effective_year is not None
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

        # C4: load exempt matches, applying the same ticker/account/year filters.
        all_exempt = repo.list_exempt_matches(
            account=account or None,
            year=effective_year,
        )
        if ticker:
            all_exempt = [em for em in all_exempt if em.ticker == ticker.upper()]

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
                "exempt_matches": all_exempt,
            }
        )

    return ctx


@router.get("/wash-sales", response_class=HTMLResponse)
def wash_sales_legacy(request: Request) -> RedirectResponse:
    """301 redirect — /wash-sales has been renamed to /tax (Phase 2).

    Old ?view=table|calendar sub-views are normalised to view=wash-sales
    so the redirect always lands on a valid /tax view.
    """
    qs = dict(request.query_params)
    if qs.get("view") in (None, "table", "calendar"):
        qs["view"] = "wash-sales"
    return RedirectResponse(url="/tax?" + urlencode(qs), status_code=301)


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
