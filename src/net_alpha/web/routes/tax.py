"""Tabbed /tax page — replaces /wash-sales as the primary tax-related route.

Views: wash-sales | harvest | budget | projection
"""

from __future__ import annotations

from datetime import date as _date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.portfolio.tax_planner import (
    MissingTaxConfig,
    TaxBrackets,
    compute_harvest_queue,
    compute_offset_budget,
    project_year_end_tax,
)
from net_alpha.prefs.profile import resolve_effective_profile
from net_alpha.pricing.service import PricingService
from net_alpha.web.dependencies import (
    get_etf_pairs,
    get_pricing_service,
    get_repository,
)

router = APIRouter()


@router.get("/tax", response_class=HTMLResponse)
def get_tax(
    request: Request,
    view: str | None = None,
    account: str | None = None,
    year: int | None = None,
    ticker: str | None = None,
    confidence: str | None = None,
    sort: str | None = None,
    order: str = "desc",
    only_harvestable: str | None = None,
    repo: Repository = Depends(get_repository),
    pricing: PricingService = Depends(get_pricing_service),
    etf_pairs: dict[str, list[str]] = Depends(get_etf_pairs),
) -> HTMLResponse:
    """Tabbed tax page. Replaces /wash-sales — preserves existing wash-sales UI as default tab.

    Accepted ``view`` values: wash-sales | table | calendar | harvest | budget | projection.
    ``table`` and ``calendar`` are synonyms for the wash-sales tab sub-views.
    """
    today = _date.today()

    # Normalise tab-level view key for context / template branching.
    # "budget" is a back-compat alias for "harvest" — the offset-budget tile
    # is now rendered above the harvest queue on the harvest tab.
    _TAB_VIEWS = {"wash-sales", "harvest", "projection"}
    _VIEW_ALIASES = {"budget": "harvest"}
    # Inner sub-views for the wash-sales tab (table / calendar toggle).
    _WASH_SUB_VIEWS = {"table", "calendar"}

    if view in _VIEW_ALIASES:
        view = _VIEW_ALIASES[view]

    prefs = repo.list_user_preferences()
    filter_id = None
    if account:
        for a in repo.list_accounts():
            if f"{a.broker}/{a.label}" == account:
                filter_id = a.id
                break
    profile = resolve_effective_profile(prefs=prefs, filter_account_id=filter_id)

    # Resolve effective view: when view is absent or invalid, use profile default.
    if view not in _TAB_VIEWS and view not in _WASH_SUB_VIEWS:
        view = profile.default_tax_tab()

    if view in _WASH_SUB_VIEWS:
        inner_view = view
        tab_view = "wash-sales"
    elif view in _TAB_VIEWS:
        inner_view = "table"
        tab_view = view
    else:
        inner_view = "table"
        tab_view = "wash-sales"

    ctx: dict = {
        "request": request,
        "view": tab_view,
        "active_page": "tax",
        "selected_account": account or "",
        "selected_year": year,
        "profile": profile,
        "page_key": "/tax",
        "account_id": filter_id,
    }

    if tab_view == "wash-sales":
        from net_alpha.web.routes.wash_sales import _wash_sales_context

        ctx.update(
            _wash_sales_context(
                repo,
                ticker=ticker,
                account=account,
                year=year,
                confidence=confidence,
                sort=sort,
                order=order,
                view=inner_view,
            )
        )
        # Override the view key in ctx with the inner view so the template toggles correctly.
        ctx["view"] = inner_view
        ctx["tab_view"] = tab_view
    elif view == "harvest":
        _falsey = ("", "0", "false", "off")
        only_harvestable_bool = only_harvestable is not None and only_harvestable.lower() not in _falsey
        rows = compute_harvest_queue(
            repo=repo,
            pricing=pricing,
            as_of=today,
            etf_pairs=etf_pairs,
            etf_replacements=request.app.state.etf_replacements,
            only_harvestable=only_harvestable_bool,
        )
        ctx["rows"] = rows
        ctx["only_harvestable"] = only_harvestable_bool
        ctx["budget"] = compute_offset_budget(repo=repo, year=today.year)
    elif view == "projection":
        cfg = request.app.state.tax_brackets_cfg
        if cfg is not None:
            brackets = TaxBrackets(
                filing_status=cfg.filing_status,
                state=cfg.state,
                federal_marginal_rate=cfg.federal_marginal_rate,
                state_marginal_rate=cfg.state_marginal_rate,
                ltcg_rate=cfg.ltcg_rate,
                qualified_div_rate=cfg.qualified_div_rate,
            )
            try:
                ctx["projection"] = project_year_end_tax(
                    repo=repo,
                    year=today.year,
                    brackets=brackets,
                )
                ctx["has_tax_config"] = True
            except MissingTaxConfig:
                ctx["projection"] = None
                ctx["has_tax_config"] = False
        else:
            ctx["projection"] = None
            ctx["has_tax_config"] = False

    return request.app.state.templates.TemplateResponse(request, "tax.html", ctx)
