"""Tabbed /tax page — replaces /wash-sales as the primary tax-related route.

Views: wash-sales | projection
(harvest and budget were moved to /positions?view=at-loss in Phase 1 IA)
"""

from __future__ import annotations

from datetime import date as _date
from decimal import Decimal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from net_alpha.config import TaxConfig, write_tax_config
from net_alpha.db.repository import Repository
from net_alpha.portfolio.tax_planner import (
    MissingTaxConfig,
    TaxBrackets,
    project_year_end_tax,
)
from net_alpha.prefs.profile import resolve_effective_profile
from net_alpha.web.dependencies import (
    get_repository,
)

router = APIRouter()


@router.get("/tax", response_class=HTMLResponse, response_model=None)
def get_tax(
    request: Request,
    view: str | None = None,
    account: str | None = None,
    year: int | None = None,
    ticker: str | None = None,
    confidence: str | None = None,
    sort: str | None = None,
    order: str = "desc",
    repo: Repository = Depends(get_repository),
) -> HTMLResponse | RedirectResponse:
    """Tabbed tax page. Replaces /wash-sales — preserves existing wash-sales UI as default tab.

    Accepted ``view`` values: wash-sales | table | calendar | projection.
    ``table`` and ``calendar`` are synonyms for the wash-sales tab sub-views.
    ``harvest`` and ``budget`` are permanently redirected to /positions?view=at-loss.
    """
    # Resolve aliases first so /tax?view=budget also redirects to /positions.
    _VIEW_ALIASES = {"budget": "harvest"}
    if view in _VIEW_ALIASES:
        view = _VIEW_ALIASES[view]

    if view == "harvest":
        params = dict(request.query_params)
        params.pop("view", None)
        params["view"] = "at-loss"
        target = f"/positions?{urlencode(params)}"
        return RedirectResponse(url=target, status_code=301)

    # Normalise tab-level view key for context / template branching.
    _TAB_VIEWS = {"wash-sales", "projection"}
    # Inner sub-views for the wash-sales tab (table / calendar toggle).
    _WASH_SUB_VIEWS = {"table", "calendar"}

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
    elif view == "projection":
        cfg = request.app.state.tax_brackets_cfg
        proj_ctx = _build_projection_ctx(request, repo, cfg)
        ctx.update(proj_ctx)

    return request.app.state.templates.TemplateResponse(request, "tax.html", ctx)


def _build_projection_ctx(
    request: Request,
    repo: Repository,
    cfg: TaxConfig | None,
) -> dict:
    """Build the template context for the projection tab body fragment."""
    today = _date.today()
    ctx: dict = {"request": request, "tax_brackets_cfg": cfg}
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
    return ctx


@router.post("/tax/projection-config", response_class=HTMLResponse)
def post_projection_config(
    request: Request,
    filing_status: str = Form(...),
    state: str = Form(...),
    federal_marginal_rate: float = Form(...),
    state_marginal_rate: float = Form(...),
    ltcg_rate: float = Form(...),
    qualified_div_rate: float = Form(...),
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    """Persist the user's tax-projection config and re-render the projection
    tab body. Replaces the manual YAML-snippet flow (Pr1)."""
    config = {
        "filing_status": filing_status,
        "state": state.upper(),
        "federal_marginal_rate": federal_marginal_rate,
        "state_marginal_rate": state_marginal_rate,
        "ltcg_rate": ltcg_rate,
        "qualified_div_rate": qualified_div_rate,
    }
    write_tax_config(config, path=request.app.state.settings.config_yaml_path)

    # Update live app.state so the next render uses the new values
    # without requiring a server restart.
    new_cfg = TaxConfig(
        filing_status=filing_status,  # type: ignore[arg-type]
        state=state.upper(),
        federal_marginal_rate=Decimal(str(federal_marginal_rate)),
        state_marginal_rate=Decimal(str(state_marginal_rate)),
        ltcg_rate=Decimal(str(ltcg_rate)),
        qualified_div_rate=Decimal(str(qualified_div_rate)),
    )
    request.app.state.tax_brackets_cfg = new_cfg

    ctx = _build_projection_ctx(request, repo, new_cfg)
    return request.app.state.templates.TemplateResponse(
        request,
        "_projection_tab.html",
        ctx,
    )
