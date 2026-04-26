from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.web.dependencies import get_repository

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    year: str | None = None,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    imports = repo.list_imports()
    all_violations = repo.all_violations()
    today = date.today()
    current_year = today.year

    year_set = {v.loss_sale_date.year for v in all_violations if v.loss_sale_date}
    year_set.add(current_year)
    available_years = sorted(year_set, reverse=True)

    selected_year: int | None
    if year == "all":
        selected_year = None
    else:
        try:
            selected_year = int(year) if year else current_year
        except ValueError:
            selected_year = current_year

    if selected_year is None:
        filtered = all_violations
        period_label = "All time"
    else:
        filtered = [v for v in all_violations if v.loss_sale_date and v.loss_sale_date.year == selected_year]
        period_label = "YTD" if selected_year == current_year else f"FY{selected_year}"

    period_disallowed = sum((v.disallowed_loss for v in filtered), start=0.0)
    period_count = len(filtered)
    open_violations = [v for v in all_violations if v.loss_sale_date and (today - v.loss_sale_date).days <= 30]

    return request.app.state.templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "imports": imports,
            "open_violations": open_violations,
            "all_violations": filtered,
            "period_disallowed": period_disallowed,
            "period_count": period_count,
            "period_label": period_label,
            "selected_year": selected_year,
            "available_years": available_years,
            "current_year": current_year,
        },
    )
