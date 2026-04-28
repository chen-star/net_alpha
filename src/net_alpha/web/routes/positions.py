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
        rows = compute_harvest_queue(
            repo=repo,
            pricing=pricing,
            as_of=today,
            etf_pairs=etf_pairs,
            etf_replacements=request.app.state.etf_replacements,
            only_harvestable=only_harvestable_bool,
        )

        def _lockout_sort_key(row):
            if row.lockout_clear is None or row.lockout_clear <= today:
                return (0, today)
            return (1, row.lockout_clear)

        rows = sorted(rows, key=_lockout_sort_key)

        ctx["rows"] = rows
        ctx["today"] = today
        ctx["only_harvestable"] = only_harvestable_bool
        ctx["budget"] = compute_offset_budget(repo=repo, year=today.year)
        ctx["harvest_form_action"] = "/positions?view=at-loss"
        ctx["harvest_form_target"] = "#positions-tab-content"
        if request.headers.get("hx-request"):
            return request.app.state.templates.TemplateResponse(
                request,
                "_positions_view_at_loss.html",
                ctx,
            )

    return request.app.state.templates.TemplateResponse(
        request,
        "positions.html",
        ctx,
    )


@router.get("/positions/pane", response_class=HTMLResponse)
def positions_pane(
    request: Request,
    sym: str,
    account_id: int | None = None,
    repo: Repository = Depends(get_repository),
    pricing: PricingService = Depends(get_pricing_service),
) -> HTMLResponse:
    """Return the side-pane body fragment for one position.

    Mounted into ``#positions-pane-body`` via HTMX from a row click on
    /positions. Phase 2 wires three sub-blocks (sim-sell preview, set-basis
    form, open-ticker link) — see Section E of the Phase 2 plan.
    """
    sym = sym.upper().strip()
    quotes = pricing.get_prices([sym])
    quote = quotes.get(sym)
    last_price = quote.price if quote and quote.price is not None else None

    return request.app.state.templates.TemplateResponse(
        request,
        "_positions_pane_body.html",
        {
            "sym": sym,
            "account_id": account_id,
            "last_price": last_price,
        },
    )
