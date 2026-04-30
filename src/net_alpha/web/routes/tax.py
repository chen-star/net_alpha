"""Tabbed /tax page — replaces /wash-sales as the primary tax-related route.

Views: wash-sales | projection
(harvest and budget were moved to /positions?view=at-loss in Phase 1 IA)
"""

from __future__ import annotations

from datetime import date as _date
from decimal import Decimal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from net_alpha.config import TaxConfig, write_tax_config
from net_alpha.db.repository import Repository
from net_alpha.explain import explain_exempt, explain_violation
from net_alpha.portfolio.tax_planner import (
    MissingTaxConfig,
    TaxBrackets,
    project_year_end_tax,
)
from net_alpha.prefs.profile import resolve_effective_profile
from net_alpha.pricing.service import PricingService
from net_alpha.web.dependencies import (
    get_pricing_service,
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
    _TAB_VIEWS = {"wash-sales", "projection", "performance"}
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
        ctx["chips_clear_urls"] = _build_chips_clear_urls(request)
    elif view == "projection":
        cfg = request.app.state.tax_brackets_cfg
        proj_ctx = _build_projection_ctx(request, repo, cfg)
        ctx.update(proj_ctx)
    elif view == "performance":
        cfg = request.app.state.tax_brackets_cfg
        perf_ctx = _build_performance_ctx(request, repo, cfg, year=year, account=account)
        ctx.update(perf_ctx)

    return request.app.state.templates.TemplateResponse(request, "tax.html", ctx)


@router.get("/tax/harvest/plan", response_class=HTMLResponse, response_model=None)
def harvest_plan(
    request: Request,
    repo: Repository = Depends(get_repository),
    pricing: PricingService = Depends(get_pricing_service),
    mode: str = "auto",
    custom_budget: str = "",
    exclude_locked: bool = True,
    pick: list[str] | None = Query(default=None),
):
    """Return the harvest plan-builder fragment.

    Modes:
      - auto: target = realized_gains_ytd + 3000
      - custom: target = custom_budget
      - manual: selection comes from `pick` query params (symbol::account_label)
    """
    from datetime import date
    from decimal import Decimal, InvalidOperation

    from net_alpha.portfolio.tax_planner import (
        TaxBrackets,
        _realized_in_year,
        _tax_saved_for,
        build_plan,
        compute_harvest_queue,
        summarize_manual_picks,
    )

    today = date.today()
    rows = compute_harvest_queue(
        repo=repo,
        pricing=pricing,
        as_of=today,
        etf_pairs=request.app.state.etf_pairs,
        etf_replacements=request.app.state.etf_replacements,
        only_harvestable=False,
    )

    cfg = request.app.state.tax_brackets_cfg
    brackets: TaxBrackets | None = None
    if cfg is not None:
        brackets = TaxBrackets(
            filing_status=cfg.filing_status,
            state=cfg.state,
            federal_marginal_rate=cfg.federal_marginal_rate,
            state_marginal_rate=cfg.state_marginal_rate,
            ltcg_rate=cfg.ltcg_rate,
            qualified_div_rate=cfg.qualified_div_rate,
        )

    _, gains_ytd = _realized_in_year(repo, today.year)

    if mode == "manual":
        picks: list[tuple[str, str]] = []
        for p in pick or []:
            if "::" in p:
                sym, acct = p.split("::", 1)
                picks.append((sym, acct))
        plan = summarize_manual_picks(
            picks=picks,
            candidates=rows,
            realized_gains_ytd=gains_ytd,
            marginal_rates=brackets,
        )
        budget_str = ""
    elif mode == "custom":
        try:
            tb = Decimal(custom_budget) if custom_budget else Decimal("0")
        except InvalidOperation:
            tb = Decimal("0")
        plan = build_plan(
            rows,
            gains_ytd,
            brackets,
            target_budget=tb,
            exclude_locked=exclude_locked,
        )
        budget_str = custom_budget
    else:
        plan = build_plan(
            rows,
            gains_ytd,
            brackets,
            target_budget=None,
            exclude_locked=exclude_locked,
        )
        budget_str = ""

    # Decorate rows with __tax_saved for the per-row column.
    for r in rows:
        r.__dict__["__tax_saved"] = _tax_saved_for(r, brackets)

    selected_keys = {(c.symbol, c.account_label) for c in plan.selected}

    return request.app.state.templates.TemplateResponse(
        request,
        "_harvest_plan.html",
        {
            "plan": plan,
            "rows": rows,
            "selected_keys": selected_keys,
            "mode": mode,
            "custom_budget": budget_str,
            "exclude_locked": exclude_locked,
            "has_tax_config": brackets is not None,
        },
    )


def _build_chips_clear_urls(request: Request) -> dict[str, str]:
    """Per-chip URLs that drop one filter key from the current query string."""
    params = dict(request.query_params)
    urls: dict[str, str] = {}
    for key in ("ticker", "account", "confidence"):
        if key in params:
            remaining = {k: v for k, v in params.items() if k != key}
            urls[key] = f"/tax?{urlencode(remaining)}" if remaining else "/tax"
    return urls


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


def _build_performance_ctx(
    request: Request,
    repo: Repository,
    cfg: TaxConfig | None,
    year: int | None,
    account: str | None,
) -> dict:
    """Build the template context for the performance tab body fragment."""
    from net_alpha.portfolio.after_tax import Period, compute_after_tax

    ctx: dict = {"request": request, "tax_brackets_cfg": cfg}
    if cfg is None:
        ctx["breakdown"] = None
        ctx["has_tax_config"] = False
        return ctx

    brackets = TaxBrackets(
        filing_status=cfg.filing_status,
        state=cfg.state,
        federal_marginal_rate=cfg.federal_marginal_rate,
        state_marginal_rate=cfg.state_marginal_rate,
        ltcg_rate=cfg.ltcg_rate,
        qualified_div_rate=cfg.qualified_div_rate,
    )

    today = _date.today()
    if year is not None:
        period_obj = Period.for_year(year)
    else:
        period_obj = Period.ytd(today.year)

    breakdown = compute_after_tax(repo, period_obj, account, brackets)
    ctx["breakdown"] = breakdown
    ctx["has_tax_config"] = True
    return ctx


@router.post("/tax/projection-config", response_class=HTMLResponse)
def post_projection_config(
    request: Request,
    filing_status: str = Form(...),
    state: str = Form(""),
    federal_marginal_rate: float = Form(...),
    state_marginal_rate: float = Form(0.0),
    ltcg_rate: float = Form(...),
    qualified_div_rate: float = Form(0.0),
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


@router.get("/tax/violation/{vid}/explain", response_class=HTMLResponse, response_model=None)
def get_violation_explain(
    request: Request,
    vid: int,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    """HTMX fragment: inline explain panel for a wash-sale violation."""
    v = repo.get_violation(vid)
    if v is None:
        raise HTTPException(status_code=404, detail="violation not found")
    e = explain_violation(v, repo=repo)
    return request.app.state.templates.TemplateResponse(
        request,
        "_violation_explain.html",
        {"e": e},
    )


@router.get("/tax/exempt/{eid}/explain", response_class=HTMLResponse, response_model=None)
def get_exempt_explain(
    request: Request,
    eid: int,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    """HTMX fragment: inline explain panel for an exempt match."""
    em = repo.get_exempt_match(eid)
    if em is None:
        raise HTTPException(status_code=404, detail="exempt match not found")
    e = explain_exempt(em, repo=repo)
    return request.app.state.templates.TemplateResponse(
        request,
        "_violation_explain.html",
        {"e": e},
    )
