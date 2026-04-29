from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from loguru import logger

from net_alpha.db.repository import Repository
from net_alpha.portfolio.positions import compute_closed_lots, open_lots_view
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

    if selected_view == "closed":
        gl_lots = repo.list_all_gl_lots()
        # Match Overview's period convention: YTD → (current_year, current_year+1);
        # a numeric year string → that year only; "lifetime" → no filter.
        period_filter: tuple[int, int] | None = None
        if selected_period == "ytd":
            period_filter = (current_year, current_year + 1)
        elif selected_period.isdigit():
            y = int(selected_period)
            period_filter = (y, y + 1)
        # selected_period == "lifetime" leaves period_filter as None.
        account_display = account if account else None
        closed_rows = compute_closed_lots(
            gl_lots,
            period=period_filter,
            account_display=account_display,
        )
        ctx["closed_rows"] = closed_rows
        ctx["closed_total_realized"] = sum(
            (r.realized_pl for r in closed_rows), Decimal("0")
        )
        if request.headers.get("hx-request"):
            return request.app.state.templates.TemplateResponse(
                request,
                "_positions_view_closed.html",
                ctx,
            )

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

        total_unrealized = sum((row.loss for row in rows), Decimal("0"))
        harvest_clear_count = sum(1 for row in rows if row.lockout_clear is None or row.lockout_clear <= today)
        replacements_count = sum(1 for row in rows if row.suggested_replacements)
        ctx["total_unrealized"] = total_unrealized
        ctx["harvest_clear_count"] = harvest_clear_count
        ctx["replacements_count"] = replacements_count

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
    /positions. Phase 2 Section E populates three sub-blocks: header,
    sim-sell preview, and set-basis form.
    """
    sym = sym.upper().strip()
    quotes = pricing.get_prices([sym])
    quote = quotes.get(sym)
    last_price = quote.price if quote and quote.price is not None else None

    # --- Resolve account display label from account_id ---
    account_label: str | None = None
    account_display: str | None = None
    if account_id is not None:
        for acct in repo.list_accounts():
            if acct.id == account_id:
                account_label = acct.label
                account_display = f"{acct.broker}/{acct.label}"
                break

    # --- Compute qty, open_basis, loss from open lots ---
    qty: Decimal | None = None
    open_basis: Decimal | None = None
    loss: Decimal | None = None
    trade_id: str | None = None  # for single-lot set-basis form

    try:
        lots = repo.get_lots_for_ticker(sym)
        trades = repo.get_trades_for_ticker(sym)

        # Filter by account if one is specified
        if account_display is not None:
            lots = [lot for lot in lots if lot.account == account_display]
            trades = [t for t in trades if t.account == account_display]

        gl_closures = repo.get_equity_gl_closures()
        gl_option_closures = repo.get_option_gl_closures()

        # Filter GL closures to the same account scope
        if account_display is not None:
            gl_closures = {k: v for k, v in gl_closures.items() if k[0] == account_display}
            gl_option_closures = {k: v for k, v in gl_option_closures.items() if k[0] == account_display}

        open_lots = open_lots_view(
            lots=lots,
            trades=trades,
            gl_closures=gl_closures,
            gl_option_closures=gl_option_closures,
        )
        # Equity-only lots (no option_details)
        equity_open = [lot for lot in open_lots if lot.option_details is None]

        if equity_open:
            qty = sum((Decimal(str(lot.quantity)) for lot in equity_open), Decimal("0"))
            open_basis = sum((Decimal(str(lot.adjusted_basis)) for lot in equity_open), Decimal("0"))
            if last_price is not None and qty:
                market_value = qty * Decimal(str(last_price))
                loss = market_value - open_basis  # positive = gain, negative = loss

            # For the set-basis form: single-lot → expose trade_id for the form
            if len(equity_open) == 1:
                trade_id = equity_open[0].trade_id
    except Exception as exc:  # noqa: BLE001 — never block the pane render
        logger.warning("positions_pane lookup failed for sym={}, account_id={}: {!r}", sym, account_id, exc)

    # --- Sim-sell realized delta ---
    # realized_delta == loss when both are computed (qty * price − open_basis).
    ctx = {
        "sym": sym,
        "account_id": account_id,
        "last_price": last_price,
        "qty": qty,
        "open_basis": open_basis,
        "loss": loss,
        "account_label": account_label,
        "realized_delta": loss,
        "trade_id": trade_id,
    }

    return request.app.state.templates.TemplateResponse(
        request,
        "_positions_pane_body.html",
        ctx,
    )
