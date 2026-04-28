from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.portfolio.tax_planner import compute_harvest_queue, compute_offset_budget
from net_alpha.prefs.profile import resolve_effective_profile
from net_alpha.pricing.service import PricingService
from net_alpha.web.dependencies import (
    get_etf_pairs,
    get_pricing_service,
    get_repository,
)

router = APIRouter()


@router.get("/positions", response_class=HTMLResponse)
def positions_page(
    request: Request,
    period: str | None = None,
    account: str | None = None,
    view: str | None = None,
    only_harvestable: str | None = None,
    repo: Repository = Depends(get_repository),
    pricing: PricingService = Depends(get_pricing_service),
    etf_pairs: dict[str, list[str]] = Depends(get_etf_pairs),
) -> HTMLResponse:
    selected_view = view or "all"
    if selected_view not in {"all", "stocks", "options", "at-loss", "closed"}:
        selected_view = "all"

    imports = repo.list_imports()
    accounts = sorted({imp.account_display for imp in imports})

    today = date.today()
    current_year = today.year
    import_years = {imp.imported_at.year for imp in imports}
    available_years = sorted(import_years | {current_year}, reverse=True)

    selected_period = period or "ytd"

    prefs = repo.list_user_preferences()
    filter_id = None
    if account:
        for a in repo.list_accounts():
            if f"{a.broker}/{a.label}" == account:
                filter_id = a.id
                break
    profile = resolve_effective_profile(prefs=prefs, filter_account_id=filter_id)
    extra_columns = profile.default_columns("holdings")

    ctx: dict = {
        "imports": imports,
        "accounts": accounts,
        "available_years": available_years,
        "current_year": current_year,
        "selected_period": selected_period,
        "selected_account": account or "",
        "group_options": "merge",
        "toolbar_action": "/positions",
        "profile": profile,
        "extra_columns": extra_columns,
        "page_key": "/positions",
        "account_id": filter_id,
        "selected_view": selected_view,
    }

    if selected_view == "at-loss":
        _falsey = ("", "0", "false", "off")
        only_harvestable_bool = only_harvestable is not None and only_harvestable.lower() not in _falsey
        ctx["rows"] = compute_harvest_queue(
            repo=repo,
            pricing=pricing,
            as_of=today,
            etf_pairs=etf_pairs,
            etf_replacements=request.app.state.etf_replacements,
            only_harvestable=only_harvestable_bool,
        )
        ctx["only_harvestable"] = only_harvestable_bool
        ctx["budget"] = compute_offset_budget(repo=repo, year=today.year)

    return request.app.state.templates.TemplateResponse(
        request,
        "positions.html",
        ctx,
    )
