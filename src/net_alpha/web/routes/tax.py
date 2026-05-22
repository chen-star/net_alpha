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
from net_alpha.web.account_filter import parse_accounts
from net_alpha.web.dependencies import (
    get_pricing_service,
    get_repository,
)
from net_alpha.web.format import dom_id_slug

router = APIRouter()


@router.get("/tax", response_class=HTMLResponse, response_model=None)
def get_tax(
    request: Request,
    view: str | None = None,
    account: list[str] = Query(default_factory=list),
    year: int | None = None,
    period: str | None = None,
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

    accounts: list[str] = parse_accounts(account)
    account_filter_active: bool = bool(accounts)
    # Legacy single-account value: kept for templates (positions/portfolio) that
    # still use selected_account (singular) in HTMX fragment URLs.
    single_account: str | None = accounts[0] if len(accounts) == 1 else None

    # Normalise tab-level view key for context / template branching.
    _TAB_VIEWS = {"wash-sales", "projection", "performance"}
    # Inner sub-views for the wash-sales tab (table / calendar toggle).
    _WASH_SUB_VIEWS = {"table", "calendar"}

    prefs = repo.list_user_preferences()
    filter_id: int | None = None
    if len(accounts) == 1:
        target_acct = accounts[0]
        for a in repo.list_accounts():
            if f"{a.broker}/{a.label}" == target_acct:
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

    accounts_available = sorted({imp.account_display for imp in repo.list_imports()})

    # Period selector resolution. Accepts:
    #   - "ytd" (default; current year)
    #   - "lifetime"
    #   - "<year>" (e.g. "2025") — also accepts the legacy ?year= query
    # Maps the user-facing ``period`` query param onto the existing ``year``
    # context — for_year(year) vs ytd(today.year) vs lifetime() — so the
    # per-tab handlers below don't need to learn a new vocabulary.
    today = _date.today()
    available_years_set: set[int] = set()
    for imp in repo.list_imports():
        try:
            available_years_set.add(imp.imported_at.year)
        except AttributeError:
            continue
    for t in repo.all_trades():
        try:
            available_years_set.add(t.date.year)
        except AttributeError:
            continue
    available_years_set.add(today.year)
    available_years = sorted(available_years_set, reverse=True)

    selected_period: str = "ytd"
    resolved_year: int | None = year
    if period:
        period_norm = period.lower().strip()
        if period_norm == "lifetime":
            selected_period = "lifetime"
            resolved_year = None  # lifetime — no year filter
            # Carry a sentinel so per-tab handlers can distinguish lifetime
            # from "no period specified" (which falls back to YTD).
        elif period_norm == "ytd":
            selected_period = "ytd"
            resolved_year = today.year
        else:
            try:
                yr = int(period_norm)
            except ValueError:
                yr = today.year
            selected_period = str(yr)
            resolved_year = yr
    elif year is not None:
        selected_period = str(year)
        resolved_year = year
    else:
        selected_period = "ytd"
        resolved_year = None  # let _build_performance_ctx fall back to ytd(today.year)

    # Distinguish "lifetime explicitly requested" from "no year specified" —
    # the Performance tab needs both to route through different Period
    # constructors (lifetime() vs ytd(today.year)).
    is_lifetime = selected_period == "lifetime"

    ctx: dict = {
        "request": request,
        "view": tab_view,
        "active_page": "tax",
        "selected_accounts": accounts,
        "accounts_available": accounts_available,
        "account_filter_active": account_filter_active,
        # Legacy single-value kept for templates that still reference selected_account.
        "selected_account": single_account or "",
        "selected_year": resolved_year,
        "selected_period": selected_period,
        "available_years": available_years,
        "current_year": today.year,
        "profile": profile,
        "page_key": "/tax",
        "account_id": filter_id,
        "has_any_tax_data": bool(repo.list_imports() or repo.all_violations() or repo.list_all_gl_lots()),
    }

    if tab_view == "wash-sales":
        from net_alpha.web.routes.wash_sales import _wash_sales_context

        # Wash-sales tab honours the page Period selector: ``year=`` (legacy)
        # still wins if explicitly supplied; otherwise fall through to the
        # resolved year (None on lifetime → no filter inside the helper).
        ws_year = year if year is not None else (None if is_lifetime else resolved_year)
        ctx.update(
            _wash_sales_context(
                repo,
                ticker=ticker,
                accounts=accounts,
                year=ws_year,
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
        # Re-inject multi-account context keys so outer ctx wins over whatever
        # _wash_sales_context emitted (they now agree, but be explicit).
        ctx["selected_accounts"] = accounts
        ctx["accounts_available"] = accounts_available
        ctx["account_filter_active"] = account_filter_active
    elif view == "projection":
        cfg = request.app.state.tax_brackets_cfg
        # Forward the Period selector's resolved year — lifetime collapses to
        # today's year inside _build_projection_ctx (projection is single-year
        # by nature).
        proj_year = resolved_year if (resolved_year is not None and not is_lifetime) else today.year
        proj_ctx = _build_projection_ctx(request, repo, cfg, year=proj_year)
        ctx.update(proj_ctx)
    elif view == "performance":
        cfg = request.app.state.tax_brackets_cfg
        perf_ctx = _build_performance_ctx(
            request,
            repo,
            cfg,
            year=resolved_year,
            accounts=accounts,
            is_lifetime=is_lifetime,
        )
        ctx.update(perf_ctx)

    return request.app.state.templates.TemplateResponse(request, "tax.html", ctx)


@router.get("/tax/harvest/plan", response_class=HTMLResponse, response_model=None)
def harvest_plan(
    request: Request,
    repo: Repository = Depends(get_repository),
    pricing: PricingService = Depends(get_pricing_service),
    account: list[str] = Query(default_factory=list),
    mode: str = "auto",
    custom_budget: str = "",
    exclude_locked: bool = True,
    pick: list[str] | None = Query(default=None),
    page: int = 1,
    page_size: int = 25,
):
    """Return the harvest plan-builder fragment.

    Modes:
      - auto: target = realized_gains_ytd + 3000
      - custom: target = custom_budget
      - manual: selection comes from `pick` query params (symbol::account_label)

    Note: compute_harvest_queue and build_plan take account_id: int | None (not
    accounts: list[str]). When multiple accounts are selected, we degrade to
    all-accounts (account_id=None). Task 11 will widen these helpers.

    Direct (non-HTMX) GETs render a bare fragment with no chrome — that's
    confusing when a user bookmarks or shares the URL. Redirect to the
    parent /positions?view=at-loss page (which embeds this fragment via
    HTMX on load), preserving the query string so deep-links survive.
    """
    if request.headers.get("HX-Request") != "true":
        qs = request.url.query
        target = "/positions?view=at-loss"
        if qs:
            target = f"{target}&{qs}"
        return RedirectResponse(url=target, status_code=303)
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

    accounts: list[str] = parse_accounts(account)
    account_filter_active: bool = bool(accounts)
    # Single-account: resolve to ID. Multi-select degrades to None (all-accounts).
    account_id: int | None = None
    if len(accounts) == 1:
        target_acct = accounts[0]
        for a in repo.list_accounts():
            if f"{a.broker}/{a.label}" == target_acct:
                account_id = a.id
                break

    today = date.today()
    rows = compute_harvest_queue(
        repo=repo,
        pricing=pricing,
        as_of=today,
        etf_pairs=request.app.state.etf_pairs,
        etf_replacements=request.app.state.etf_replacements,
        account_id=account_id,
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

    tax_saved_by_key = {(r.symbol, r.account_label): _tax_saved_for(r, brackets) for r in rows}

    selected_keys = {(c.symbol, c.account_label) for c in plan.selected}

    page_size_norm = page_size if page_size in (10, 25, 50, 100) else 25
    page_norm = max(1, page)
    total_rows = len(rows)
    total_pages = max(1, (total_rows + page_size_norm - 1) // page_size_norm)
    page_norm = min(page_norm, total_pages)
    start_idx = (page_norm - 1) * page_size_norm
    end_idx = start_idx + page_size_norm
    rows_page = rows[start_idx:end_idx]
    pagination = {
        "page": page_norm,
        "page_size": page_size_norm,
        "total_pages": total_pages,
        "total_rows": total_rows,
        "page_size_options": (10, 25, 50, 100),
    }

    has_tax_config = brackets is not None

    # A2.3: HTMX-target-aware response. When the summary is the target,
    # return only the summary partial plus OOB fragments for the per-row
    # tax-saved cells (no full table re-render → no scroll jump).
    hx_target = request.headers.get("HX-Target") or ""
    if hx_target == "harvest-summary":
        oob_cells_parts: list[str] = []
        if has_tax_config:
            for row in rows:
                key = (row.symbol, row.account_label)
                ts = tax_saved_by_key.get(key)
                if ts is None:
                    continue
                acct_slug = dom_id_slug(row.account_label)
                cell_id = f"tax-saved-{row.symbol}-{acct_slug}"
                oob_cells_parts.append(
                    f'<td id="{cell_id}" hx-swap-oob="true" class="r num"><span class="text-pos">${ts:.2f}</span></td>'
                )
        return request.app.state.templates.TemplateResponse(
            request,
            "_harvest_summary.html",
            {
                "plan": plan,
                "rows": rows,
                "mode": mode,
                "custom_budget": budget_str,
                "exclude_locked": exclude_locked,
                "has_tax_config": has_tax_config,
                "oob_cells": "".join(oob_cells_parts),
            },
        )

    return request.app.state.templates.TemplateResponse(
        request,
        "_harvest_plan.html",
        {
            "plan": plan,
            "rows": rows,
            "rows_page": rows_page,
            "selected_keys": selected_keys,
            "tax_saved_by_key": tax_saved_by_key,
            "mode": mode,
            "custom_budget": budget_str,
            "exclude_locked": exclude_locked,
            "has_tax_config": has_tax_config,
            "pagination": pagination,
            "picks": pick or [],
            "account_filter_active": account_filter_active,
            "selected_accounts": accounts,
        },
    )


def _build_chips_clear_urls(request: Request) -> dict[str, str]:
    """Per-chip URLs that drop one filter key from the current query string.

    Uses multi_items() so repeated keys (e.g. ?account=A&account=B) are
    preserved correctly — dict(query_params) would collapse them to the last value.
    """
    params = list(request.query_params.multi_items())
    urls: dict[str, str] = {}
    for key in ("ticker", "account", "confidence"):
        if any(k == key for k, _ in params):
            remaining = [(k, v) for k, v in params if k != key]
            urls[key] = f"/tax?{urlencode(remaining)}" if remaining else "/tax"
    return urls


def _build_projection_ctx(
    request: Request,
    repo: Repository,
    cfg: TaxConfig | None,
    year: int | None = None,
) -> dict:
    """Build the template context for the projection tab body fragment.

    ``year`` honours the page-level Period selector. Lifetime/YTD/None all
    fall back to the current tax year — projection is inherently a single-
    year forward look, so a multi-year view doesn't apply here.
    """
    today = _date.today()
    target_year = year if year is not None else today.year
    ctx: dict = {"request": request, "tax_brackets_cfg": cfg, "projection_year": target_year}
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
                year=target_year,
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
    accounts: list[str],
    is_lifetime: bool = False,
) -> dict:
    """Build the template context for the performance tab body fragment."""
    from net_alpha.portfolio.after_tax import Period, compute_after_tax
    from net_alpha.portfolio.carryforward import get_effective_carryforward

    today = _date.today()
    if is_lifetime:
        period_obj = Period.lifetime()
    elif year is not None and year != today.year:
        period_obj = Period.for_year(year)
    else:
        period_obj = Period.ytd(today.year)

    account_filter_active: bool = bool(accounts)

    # Load §1256 year-end MTM rows — available regardless of tax config.
    mtm_rows = repo.section_1256_mtm_rows(period_obj, accounts=accounts or None)
    mtm_rows.sort(key=lambda r: (r.tax_year, r.ticker, r.position_key))

    ctx: dict = {
        "request": request,
        "tax_brackets_cfg": cfg,
        "mtm_rows": mtm_rows,
        "account_filter_active": account_filter_active,
    }
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

    # Apply prior-year carryforward (override-wins) when the period is
    # year-scoped. Lifetime period (year is None) gets no carryforward —
    # carryforward semantics don't apply to a multi-year aggregate view.
    cf = get_effective_carryforward(repo, period_obj.year) if period_obj.year is not None else None

    breakdown = compute_after_tax(repo, period_obj, brackets=brackets, accounts=accounts or None, carryforward=cf)
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
