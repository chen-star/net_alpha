from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from loguru import logger
from starlette.responses import Response

from net_alpha.db.repository import Repository
from net_alpha.engine.simulator import simulate_sell
from net_alpha.models.domain import Lot
from net_alpha.portfolio.carryforward import get_effective_carryforward
from net_alpha.portfolio.cash_flow import compute_cash_kpis
from net_alpha.portfolio.models import PositionRow
from net_alpha.portfolio.positions import (
    compute_closed_lots,
    compute_open_positions,
    compute_open_short_option_positions,
    open_lots_view,
)
from net_alpha.portfolio.tax_planner import compute_harvest_queue, compute_offset_budget
from net_alpha.prefs.profile import resolve_effective_profile
from net_alpha.pricing.service import PricingService
from net_alpha.targets.models import TargetUnit
from net_alpha.targets.view import PlanView, build_plan_view
from net_alpha.web.account_filter import exclude_positions_sentinel, parse_accounts
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
    account: list[str] = Query(default_factory=list),
    view: str | None = None,
    only_harvestable: str | None = None,
    page: int = 1,
    page_size: int = 25,
    repo: Repository = Depends(get_repository),
    pricing: PricingService = Depends(get_pricing_service),
    etf_pairs: dict[str, list[str]] = Depends(get_etf_pairs),
) -> HTMLResponse:
    accounts: list[str] = parse_accounts(account)
    account_filter_active: bool = bool(accounts)

    selected_view = view or "all"
    if selected_view not in {"all", "stocks", "options", "at-loss", "closed", "plan"}:
        selected_view = "all"

    if page_size not in (10, 25, 50, 100):
        page_size = 25

    imports = repo.list_imports()
    accounts_available = exclude_positions_sentinel(sorted({imp.account_display for imp in imports}))

    today = dt.date.today()
    current_year = today.year
    import_years = {imp.imported_at.year for imp in imports}
    available_years = sorted(import_years | {current_year}, reverse=True)

    selected_period = period or "ytd"

    # Resolve profile: single-account mode degrades to taxpayer-level for multi.
    prefs = repo.list_user_preferences()
    filter_id: int | None = None
    if len(accounts) == 1:
        target_acct = accounts[0]
        for a in repo.list_accounts():
            if f"{a.broker}/{a.label}" == target_acct:
                filter_id = a.id
                break
    profile = resolve_effective_profile(prefs=prefs, filter_account_id=filter_id)
    extra_columns = profile.default_columns("holdings")

    targets = repo.list_targets()
    target_count = len(targets)

    ctx: dict = {
        "imports": imports,
        "accounts_available": accounts_available,
        "selected_accounts": accounts,
        "account_filter_active": account_filter_active,
        "available_years": available_years,
        "current_year": current_year,
        "selected_period": selected_period,
        "selected_account": accounts[0] if len(accounts) == 1 else "",
        "group_options": "merge",
        "toolbar_action": "/positions",
        "profile": profile,
        "extra_columns": extra_columns,
        "page_key": "/positions",
        "account_id": filter_id,
        "selected_view": selected_view,
        "target_count": target_count,
        "page": max(1, page),
        "page_size": page_size,
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
        closed_rows = compute_closed_lots(
            gl_lots,
            period=period_filter,
            accounts=accounts or None,
        )
        # Sort by closed_date desc so most recent lots appear on page 1.
        closed_rows = sorted(closed_rows, key=lambda r: r.closed_date, reverse=True)

        page_size_norm = page_size if page_size in (10, 25, 50, 100) else 25
        page_norm = max(1, page)
        total_rows = len(closed_rows)
        total_pages = max(1, (total_rows + page_size_norm - 1) // page_size_norm)
        page_norm = min(page_norm, total_pages)
        start_idx = (page_norm - 1) * page_size_norm
        end_idx = start_idx + page_size_norm
        ctx["closed_rows_total"] = len(closed_rows)  # full count for the header
        ctx["closed_total_realized"] = sum((r.realized_pl for r in closed_rows), Decimal("0"))
        ctx["closed_rows"] = closed_rows[start_idx:end_idx]
        ctx["pagination"] = {
            "page": page_norm,
            "page_size": page_size_norm,
            "total_pages": total_pages,
            "total_rows": total_rows,
            "page_size_options": (10, 25, 50, 100),
            "view": "closed",
        }
        if request.headers.get("hx-request"):
            return request.app.state.templates.TemplateResponse(
                request,
                "_positions_view_closed.html",
                ctx,
            )

    if selected_view == "at-loss":
        _falsey = ("", "0", "false", "off")
        # Default to True (checkbox checked) when the param is absent.
        only_harvestable_bool = only_harvestable is None or only_harvestable.lower() not in _falsey
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
        ctx["budget"] = compute_offset_budget(
            repo=repo,
            year=today.year,
            carryforward=get_effective_carryforward(repo, today.year),
        )
        ctx["harvest_form_action"] = "/positions?view=at-loss"
        ctx["harvest_form_target"] = "#positions-tab-content"
        if request.headers.get("hx-request"):
            return request.app.state.templates.TemplateResponse(
                request,
                "_positions_view_at_loss.html",
                ctx,
            )

    if selected_view == "plan":
        import dataclasses as _dc

        selected_tag_param = request.query_params.get("tag") or None
        sort_key_param = request.query_params.get("sort") or "manual"
        plan_view, _pos_by_sym = _build_plan_view_for_request(
            repo, pricing, accounts, selected_tag_param, sort_key_param
        )

        page_size_norm = page_size if page_size in (10, 25, 50, 100) else 25
        page_norm = max(1, page)
        total_rows = len(plan_view.rows)
        total_pages = max(1, (total_rows + page_size_norm - 1) // page_size_norm)
        page_norm = min(page_norm, total_pages)
        start_idx = (page_norm - 1) * page_size_norm
        end_idx = start_idx + page_size_norm
        plan_view = _dc.replace(plan_view, rows=list(plan_view.rows)[start_idx:end_idx])

        change_states, watch_results = _compute_change_states(plan_view, _pos_by_sym, repo)

        ctx["plan_view"] = plan_view
        ctx["watch_by_target_id"] = watch_results
        ctx["change_states"] = change_states
        ctx["pagination"] = {
            "page": page_norm,
            "page_size": page_size_norm,
            "total_pages": total_pages,
            "total_rows": total_rows,
            "page_size_options": (10, 25, 50, 100),
        }
        if request.headers.get("hx-request"):
            return request.app.state.templates.TemplateResponse(
                request,
                "_positions_view_plan.html",
                ctx,
            )

    return request.app.state.templates.TemplateResponse(
        request,
        "positions.html",
        ctx,
    )


def _pane_lot_info(
    open_equity_lots: list[Lot],
    last_price: float | None,
    today: dt.date,
    ws_implicated_trade_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Compute per-lot status fields used by the ST/LT clock and the lot
    ladder. Returns a dict with keys:

    - `lots`: list[dict] one per lot, with fields: date, qty, adj_basis,
      unrealized, status ("ST" | "LT" | "TACKED" | "WS"), days_to_lt,
      is_tacked, is_ws_implicated.
    - `clock`: dict | None — {"min_days_to_lt": int} if any ST lot is
      ≤90d from LT, else None.

    Status precedence: TACKED > WS > LT > ST.
    TACKED signals the holding-period side-effect of §1223(4); WS signals
    the cost-basis inflation from §1091(d) on a non-tacked lot (rare —
    requires partial overlap where basis was adjusted without tacking).
    When a lot is both tacked and WS-implicated, TACKED wins (the
    holding-period concern is more material to the user).

    ws_implicated_trade_ids: set of replacement_trade_id values from open
    WashSaleViolation rows for this ticker. A lot is WS-implicated when
    its trade_id is a member of this set.
    """
    rows: list[dict] = []
    min_days: int | None = None
    for lot in open_equity_lots:
        effective_acquired = getattr(lot, "tacked_acquired_date", None) or lot.date
        if isinstance(effective_acquired, str):
            effective_acquired = dt.date.fromisoformat(effective_acquired)
        held_days = (today - effective_acquired).days
        is_lt = held_days > 365
        days_to_lt = 366 - held_days if not is_lt else 0
        is_tacked = getattr(lot, "tacked_acquired_date", None) is not None

        # WS-implicated: lot's trade_id appears as a replacement_trade_id in
        # at least one WashSaleViolation — meaning §1091(d) rolled a
        # disallowed loss into this lot's adjusted_basis.
        is_ws_implicated = ws_implicated_trade_ids is not None and lot.trade_id in ws_implicated_trade_ids

        unrealized: Decimal | None = None
        if last_price is not None:
            unrealized = Decimal(str(last_price)) * Decimal(str(lot.quantity)) - Decimal(str(lot.adjusted_basis))

        # Status precedence: TACKED > WS > LT > ST.
        if is_tacked:
            status = "TACKED"
        elif is_ws_implicated:
            status = "WS"
        elif is_lt:
            status = "LT"
        else:
            status = "ST"
        rows.append(
            {
                "date": effective_acquired,
                "qty": Decimal(str(lot.quantity)),
                "adj_basis": Decimal(str(lot.adjusted_basis)),
                "unrealized": unrealized,
                "status": status,
                "days_to_lt": days_to_lt,
                "is_tacked": is_tacked,
                "is_ws_implicated": is_ws_implicated,
                "account": getattr(lot, "account", ""),
            }
        )

        if not is_lt and 0 < days_to_lt <= 90:
            if min_days is None or days_to_lt < min_days:
                min_days = days_to_lt

    clock = {"min_days_to_lt": min_days} if min_days is not None else None
    return {"lots": rows, "clock": clock}


def _find_safe_sell_qty(
    *,
    sym: str,
    accounts: list,
    qty: Decimal,
    price: Decimal,
    existing_lots: list,
    recent_trades: list,
) -> Decimal | None:
    """Binary-search for the largest K in [1, qty] where simulate_sell(K) is clean.

    Returns the safe qty as a Decimal, or None if no safe qty exists (i.e., even
    selling 1 share triggers a wash sale — all lots are loss lots).

    Rationale: simulate_sell uses FIFO lot consumption, so `is_loss` (and thus
    `would_trigger_wash_sale`) is qty-sensitive when the position contains a mix
    of gain lots (consumed first by FIFO) and loss lots.  Selling up to the gain
    lot boundary is clean; selling beyond it into the loss lots triggers.

    The bisection runs O(log₂(qty)) calls — typically 10–20 for a 1000-share
    position. Each call is cheap (single-symbol window) and stays under 100ms total.
    """

    def _triggers(k: Decimal) -> bool:
        opts = simulate_sell(
            ticker=sym,
            qty=k,
            price=price,
            accounts=accounts,
            existing_lots=existing_lots,
            recent_trades=recent_trades,
        )
        return any(opt.would_trigger_wash_sale for opt in opts)

    # Fast-path: even 1 share triggers → no safe qty exists.
    if _triggers(Decimal("1")):
        return None

    # Binary search: lo is known-clean, hi is known-trigger (qty).
    # Find the largest clean K.
    lo = Decimal("1")
    hi = qty
    # qty is known to trigger (caller verified this before calling us).
    # Quantities are integers (whole shares or whole contracts).
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if _triggers(mid):
            hi = mid
        else:
            lo = mid

    # lo is the largest K where simulate_sell is clean.
    return lo


def _pane_ws_outlook(
    *,
    sym: str,
    account_display: str | None,
    qty: Decimal | None,
    last_price: float | None,
    repo: Repository,
) -> dict[str, Any]:
    """Compute wash-sale outlook for the pane using simulate_sell.

    Returns a dict with keys:
      - state: "clean" | "trigger" | "partial" | "error" | "skipped"
      - message: str (rendered text; empty in clean state)
      - replacement: str | None (one-line footnote when trigger)
      - safe_qty: Decimal | None (only set in partial state)

    SimulationOption fields used (verified from engine/simulator.py):
      - would_trigger_wash_sale: bool
      - realized_pnl: Decimal  (negative = loss; used as disallowed amount)
      - blocking_buys: list[Trade]  (first entry provides replacement footnote)
      - confidence: str
    """
    if qty is None or qty <= 0 or last_price is None:
        return {"state": "skipped", "message": "", "replacement": None, "safe_qty": None}

    try:
        accounts = repo.list_accounts()
        # Filter to the specific account if the pane is scoped to one
        if account_display is not None:
            accounts = [a for a in accounts if a.display() == account_display]

        existing_lots = repo.all_lots()
        recent_trades = repo.all_trades()
        price_dec = Decimal(str(last_price))

        options = simulate_sell(
            ticker=sym,
            qty=qty,
            price=price_dec,
            accounts=accounts,
            existing_lots=existing_lots,
            recent_trades=recent_trades,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("ws_outlook failed for sym={}, account_display={}: {!r}", sym, account_display, exc)
        return {
            "state": "error",
            "message": "Wash-sale outlook unavailable",
            "replacement": None,
            "safe_qty": None,
        }

    # Aggregate across all account options: trigger if any has a blocking buy
    triggering = [opt for opt in options if opt.would_trigger_wash_sale]
    if not triggering:
        return {"state": "clean", "message": "", "replacement": None, "safe_qty": None}

    # Try partial state — find the largest K where selling K shares is clean.
    # This is reachable when the position has gain lots (FIFO-first) followed by
    # loss lots: selling only into the gain lots never triggers.
    try:
        safe_qty = _find_safe_sell_qty(
            sym=sym,
            accounts=accounts,
            qty=qty,
            price=price_dec,
            existing_lots=existing_lots,
            recent_trades=recent_trades,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("ws_outlook bisection failed for sym={}: {!r}", sym, exc)
        safe_qty = None

    if safe_qty is not None and safe_qty > 0:
        msg = f"Selling up to {safe_qty:g} of {qty:g} today is safe; selling more triggers a wash sale."
        return {"state": "partial", "message": msg, "replacement": None, "safe_qty": safe_qty}

    # Compute proportional disallowed loss for each triggering option.
    # blocking_buys may cover only M of the N shares sold — only (M/N) × loss
    # is actually disallowed under IRS wash-sale rules.
    sold_qty_dec = qty if qty and qty > 0 else Decimal("0")
    total_disallowed = Decimal("0")
    for opt in triggering:
        if opt.realized_pnl >= 0:
            continue
        blocking_qty_total = sum(Decimal(str(b.quantity)) for b in opt.blocking_buys)
        proportion = min(blocking_qty_total / sold_qty_dec, Decimal("1")) if sold_qty_dec > 0 else Decimal("0")
        total_disallowed += proportion * abs(opt.realized_pnl)
    disallowed_amt = total_disallowed
    message = f"Selling today would trigger a wash sale — ~${disallowed_amt:,.2f} disallowed loss."

    # Build replacement footnote from the first blocking buy found
    replacement: str | None = None
    for opt in triggering:
        if opt.blocking_buys:
            first_buy = opt.blocking_buys[0]
            replacement = f"Replacement buy: {first_buy.account} on {first_buy.date}"
            break

    return {"state": "trigger", "message": message, "replacement": replacement, "safe_qty": None}


def _build_pane_ctx(
    sym: str,
    account_id: int | None,
    repo: Repository,
    pricing: PricingService,
) -> dict[str, Any]:
    """Build the template context dict for the positions side-pane.

    Extracted so all three pane endpoints (main body, sim partial, basis
    partial) can share the same context-building logic without duplication.
    Does not call TemplateResponse — callers are responsible for rendering.
    """
    sym = sym.upper().strip()
    today = dt.date.today()
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
    # Transfer-context for the inline set-basis form. We always expose
    # trade_id (whether 1 or N lots) so the form can render a tiered UI;
    # transfer_qty/transfer_date are only meaningful for transfer rows.
    transfer_qty: float | None = None
    transfer_date: dt.date | None = None
    equity_open: list = []  # initialized here so it's always defined after the try
    recent_trades: list = []  # initialized here so it's always defined after the try
    cross_account: bool = False  # set inside try if 2+ accounts hold sym

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

        # Cross-account detection: if no specific account was requested and the
        # symbol is held in 2+ accounts, surface that to the header and ladder.
        distinct_open_accounts: set[str] = {lot.account for lot in equity_open}
        if account_id is None and len(distinct_open_accounts) >= 2:
            account_label = f"Across {len(distinct_open_accounts)} accounts"
            cross_account = True
        else:
            cross_account = False

        if equity_open:
            qty = sum((Decimal(str(lot.quantity)) for lot in equity_open), Decimal("0"))
            open_basis = sum((Decimal(str(lot.adjusted_basis)) for lot in equity_open), Decimal("0"))
            if last_price is not None and qty:
                market_value = qty * Decimal(str(last_price))
                loss = market_value - open_basis  # positive = gain, negative = loss

            # For the set-basis form: pick any open transfer_in lot (set or
            # unset) so the user can RE-EDIT a previously-saved basis without
            # reimporting. `Lot` doesn't carry basis_source, so look up the
            # parent Trade by trade_id. Unset lots come first so the form
            # defaults to addressing them. When the parent belongs to a
            # transfer group (already split), surface the original transfer
            # quantity and broker-statement date so the multi-lot variant can
            # validate against the full group.
            transfer_lots: list[tuple] = []
            for lot in equity_open:
                parent = repo.get_trade_by_id(int(lot.trade_id))
                if parent is not None and parent.basis_source == "transfer_in":
                    transfer_lots.append((lot, parent, parent.transfer_basis_user_set))
            transfer_lots.sort(key=lambda triple: triple[2])  # unset (False) first
            if transfer_lots:
                primary_lot, primary_trade, _ = transfer_lots[0]
                trade_id = primary_lot.trade_id
                # Pass the segment's own quantity so the single-lot form's
                # per-share preview is correct. The "+ Split into multiple
                # lots" link reloads the multi-lot fragment, which queries
                # the full group total on its own.
                transfer_qty = primary_trade.quantity
                transfer_date = primary_trade.transfer_date or primary_trade.date
            elif len(equity_open) == 1:
                trade_id = equity_open[0].trade_id

        # --- Recent activity: last 5 trades on sym + account scope ---
        # Reuses the already-fetched + filtered `trades` list — no extra DB call.
        _recent = sorted(trades, key=lambda t: t.date, reverse=True)
        recent_trades = _recent[:5]
    except Exception as exc:  # noqa: BLE001 — never block the pane render
        logger.warning("positions_pane lookup failed for sym={}, account_id={}: {!r}", sym, account_id, exc)

    # --- WS-implicated lot IDs: lots referenced as the replacement leg of
    # a §1091(d) DEFERRED wash sale (i.e., the disallowed loss was rolled
    # into the replacement lot's basis). We join via trade_id:
    # WashSaleViolation.replacement_trade_id == Lot.trade_id.
    #
    # Filter to kind="deferred" only — `permanent_ira` violations (Rev. Rul.
    # 2008-5) do NOT inflate the IRA replacement lot's adjusted_basis (the
    # engine skips that mutation for tax-advantaged replacement legs), so
    # the "basis inflated by §1091(d)" tooltip would be false on those rows.
    ws_implicated_trade_ids: set[str] = set()
    try:
        violations = repo.get_violations_for_ticker(sym)
        ws_implicated_trade_ids = {
            v.replacement_trade_id
            for v in violations
            if v.replacement_trade_id is not None and getattr(v, "kind", "deferred") == "deferred"
        }
    except Exception:  # noqa: BLE001
        logger.warning("ws-implicated lookup failed for sym={}", sym)

    # --- ST→LT clock + lot ladder data ---
    lot_info = _pane_lot_info(
        open_equity_lots=equity_open,
        last_price=last_price,
        today=today,
        ws_implicated_trade_ids=ws_implicated_trade_ids,
    )

    # --- Header ST/LT pill ---
    # Aggregate per-lot statuses into a single header label. ST means all
    # lots are short-term; LT means all are long-term; ST/LT means mixed.
    #
    # TACKED status (§1223(4)) doesn't directly imply LT — tacking shifts
    # the effective acquired date back to the original lot's date, which
    # may still be < 365d ago. Discriminate using `days_to_lt`: a TACKED
    # lot is effectively LT only when `days_to_lt == 0` (the helper sets
    # that field to 0 only when `held_days > 365`).
    def _eff_class(row: dict[str, Any]) -> str:
        if row["status"] in ("TACKED", "WS"):
            # Both TACKED and WS are overlay signals — the underlying ST/LT
            # classification still follows days_to_lt for the header pill.
            return "LT" if row["days_to_lt"] == 0 else "ST"
        return row["status"]  # already "ST" or "LT"

    _eff_classes = {_eff_class(r) for r in lot_info["lots"]}
    if not _eff_classes:
        header_status = None
    elif _eff_classes == {"ST"}:
        header_status = "ST"
    elif _eff_classes == {"LT"}:
        header_status = "LT"
    else:
        header_status = "ST/LT"

    # --- Wash-sale outlook ---
    ws_outlook = _pane_ws_outlook(
        sym=sym,
        account_display=account_display,
        qty=qty,
        last_price=last_price,
        repo=repo,
    )

    # --- Sim-sell realized delta ---
    # realized_delta == loss when both are computed (qty * price − open_basis).
    # cross_account is set inside the try block above; if the try threw it
    # stays False (the safe default — no grouping).
    distinct_account_displays: list[str] = sorted({row["account"] for row in lot_info["lots"]}) if cross_account else []
    return {
        "sym": sym,
        "account_id": account_id,
        "last_price": last_price,
        "qty": qty,
        "open_basis": open_basis,
        "loss": loss,
        "account_label": account_label,
        "realized_delta": loss,
        "trade_id": trade_id,
        "transfer_qty": transfer_qty,
        "transfer_date": transfer_date,
        "lt_clock": lot_info["clock"],
        "lot_rows": lot_info["lots"],
        "header_status": header_status,
        "ws_outlook": ws_outlook,
        "recent_trades": recent_trades,
        "cross_account": cross_account,
        "distinct_account_displays": distinct_account_displays,
    }


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
    ctx = _build_pane_ctx(sym=sym, account_id=account_id, repo=repo, pricing=pricing)
    return request.app.state.templates.TemplateResponse(
        request,
        "_positions_pane_body.html",
        ctx,
    )


@router.get("/positions/pane/sim", response_class=HTMLResponse)
def positions_pane_sim(
    request: Request,
    sym: str,
    action: str = "sell",
    account_id: int | None = None,
    repo: Repository = Depends(get_repository),
    pricing: PricingService = Depends(get_pricing_service),
) -> HTMLResponse:
    """Return the sim-preview partial bound to the open qty by default.
    Used by the action-row Sim sell button (HTMX outlet swap).
    Buy mode is handled by a direct link to /sim — only 'sell' is valid here."""
    if action != "sell":
        raise HTTPException(status_code=400, detail="action must be 'sell'")
    ctx = _build_pane_ctx(sym=sym, account_id=account_id, repo=repo, pricing=pricing)
    ctx["action_pref"] = action
    return request.app.state.templates.TemplateResponse(
        request,
        "_positions_pane_sim_preview.html",
        ctx,
    )


@router.get("/positions/pane/basis", response_class=HTMLResponse)
def positions_pane_basis(
    request: Request,
    sym: str,
    account_id: int | None = None,
    repo: Repository = Depends(get_repository),
    pricing: PricingService = Depends(get_pricing_service),
) -> HTMLResponse:
    """Return the set-basis form partial. Used by the action-row Set
    basis button (HTMX outlet swap)."""
    ctx = _build_pane_ctx(sym=sym, account_id=account_id, repo=repo, pricing=pricing)
    return request.app.state.templates.TemplateResponse(
        request,
        "_positions_pane_set_basis.html",
        ctx,
    )


# ---------------------------------------------------------------------------
# Plan-view helpers (shared by GET ?view=plan, POST /plan/target, DELETE)
# ---------------------------------------------------------------------------


def _build_plan_diff_rows(
    plan_view: PlanView,
    pos_by_sym: dict[str, PositionRow],
    watch_results: dict,
) -> list:
    """Build PlanDiffRow per visible plan-view row.

    Extracted so both the diff path (_compute_change_states) and the snapshot
    path (plan_mark_seen) can reuse the field mapping. PlanDiffRow and
    SnapshotRow have identical fields; SnapshotRow can be constructed from a
    PlanDiffRow via SnapshotRow(**asdict(r)).
    """
    from net_alpha.portfolio.plan_diff import PlanDiffRow, compute_pl_bucket

    out: list[PlanDiffRow] = []
    for r in plan_view.rows:
        pos = pos_by_sym.get(r.symbol)
        unrealized = float(pos.unrealized_pl) if pos and pos.unrealized_pl is not None else 0.0
        basis = float(pos.open_cost) if pos else 0.0
        watch = watch_results.get(r.symbol)
        severity = watch.severity if watch else "green"
        out.append(
            PlanDiffRow(
                ticker=r.symbol,
                target_kind=str(r.target_unit),
                target_value=float(r.target_amount),
                risk_pill=severity,
                pl_bucket=compute_pl_bucket(unrealized, basis),
            )
        )
    return out


def _compute_change_states(
    plan_view: PlanView,
    pos_by_sym: dict[str, PositionRow],
    repo: Repository,
) -> tuple[dict[str, str | None], dict]:
    """Per-ticker change_state + the watch_results dict (returned for template
    reuse so callers don't query watch_results_by_target() twice).

    Returns a tuple of (change_states, watch_results) where:
    - change_states: dict keyed by symbol; values are "new" / "changed" / None.
    - watch_results: raw dict from repo.watch_results_by_target().

    Operates on the rows currently in plan_view (call after pagination so only
    visible rows are diffed).
    """
    from net_alpha.portfolio.plan_diff import diff_plan

    watch_results = repo.watch_results_by_target()
    diff_rows = _build_plan_diff_rows(plan_view, pos_by_sym, watch_results)
    snapshot = repo.read_plan_snapshot()
    return diff_plan(diff_rows, snapshot), watch_results


def _build_plan_view_for_request(
    repo: Repository,
    pricing: PricingService,
    accounts: list[str],
    selected_tag: str | None = None,
    sort_key: str = "manual",
) -> tuple[PlanView, dict[str, PositionRow]]:
    """Compute the PlanView used by both GET ?view=plan and the POST/DELETE
    fragment refreshes. Pulls trades, lots, prices, cash events, CSP collateral,
    free cash, then calls build_plan_view. Returns (plan_view, pos_by_sym)."""
    if sort_key == "manual":
        targets = repo.list_targets_by_manual_order()
    else:
        targets = repo.list_targets()
    trades = repo.all_trades()
    lots = repo.all_lots()
    gl_closures = repo.get_equity_gl_closures()
    gl_option_closures = repo.get_option_gl_closures()
    all_lot_tickers = sorted({lot.ticker for lot in lots if lot.option_details is None})
    quote_symbols = sorted(set(all_lot_tickers) | {t.symbol for t in targets})
    prices = pricing.get_prices(quote_symbols)

    pos_rows = compute_open_positions(
        trades=trades,
        lots=lots,
        prices=prices,
        period=None,
        accounts=accounts or None,
        include_closed=False,
        gl_closures=gl_closures,
        gl_option_closures=gl_option_closures,
        gl_lots=repo.list_all_gl_lots(),
    )
    pos_by_sym = {r.symbol: r for r in pos_rows}
    quotes_by_sym = {sym: q.price for sym, q in prices.items()}

    cash_events = repo.list_cash_events(account_id=None)
    _acct_filter = set(accounts) if accounts else None
    if _acct_filter:
        cash_events = [e for e in cash_events if e.account in _acct_filter]
    holdings_value = sum(
        ((r.market_value or Decimal("0")) for r in pos_rows),
        start=Decimal("0"),
    )
    cash_kpis = compute_cash_kpis(
        events=cash_events,
        trades=trades,
        holdings_value=holdings_value,
        period=None,
    )

    scoped_trades_for_shorts = [t for t in trades if t.account in _acct_filter] if _acct_filter else trades
    open_shorts = compute_open_short_option_positions(
        scoped_trades_for_shorts,
        gl_option_closures=gl_option_closures,
    )
    cash_secured_total = sum((s.cash_secured for s in open_shorts), start=Decimal("0"))
    free_cash = cash_kpis.cash_balance - cash_secured_total

    plan_view = build_plan_view(
        targets=targets,
        positions_by_symbol=pos_by_sym,
        quotes_by_symbol=quotes_by_sym,
        free_cash=free_cash,
        selected_tag=selected_tag,
        sort_key=sort_key,
    )
    return plan_view, pos_by_sym


def _modal_error(request: Request, msg: str, status: int) -> HTMLResponse:
    response = request.app.state.templates.TemplateResponse(
        request,
        "_positions_plan_modal.html",
        {"_target": None, "error": msg, "all_tags": []},
    )
    response.status_code = status
    response.headers["HX-Retarget"] = "#plan-modal-backdrop"
    response.headers["HX-Reswap"] = "outerHTML"
    return response


async def _plan_toolbar_state(request: Request) -> dict:
    """Extract the Plan-view toolbar state from a mutation request.

    Mutations (upsert / delete / tag add+remove / reorder) re-render the
    plan body and must preserve account / tag / sort / page / page_size /
    period selections — otherwise every edit silently snaps the toolbar
    back to defaults (All / no tag / manual / page 1 / 25 / YTD). Form
    data wins where present; query params are the fallback for HX-Boosted
    requests where the form omits a key.
    """
    form_data = await request.form()

    def _pick(name: str) -> str | None:
        v = form_data.get(name) or request.query_params.get(name)
        return v.strip() if isinstance(v, str) and v.strip() else None

    raw_accounts: list[str] = list(form_data.getlist("account")) + list(request.query_params.getlist("account"))
    page_raw = _pick("page")
    try:
        page = max(1, int(page_raw)) if page_raw else 1
    except ValueError:
        page = 1
    ps_raw = _pick("page_size")
    try:
        page_size = int(ps_raw) if ps_raw else 25
    except ValueError:
        page_size = 25
    sort_key = _pick("sort") or "manual"
    selected_period = _pick("period") or "ytd"
    return {
        "accounts": parse_accounts(raw_accounts) or None,
        "selected_tag": _pick("tag"),
        "sort_key": sort_key,
        "page": page,
        "page_size": page_size,
        "selected_period": selected_period,
    }


def _render_plan_body(
    request: Request,
    repo: Repository,
    pricing: PricingService,
    accounts: list[str] | None = None,
    page: int = 1,
    page_size: int = 25,
    selected_tag: str | None = None,
    sort_key: str = "manual",
    selected_period: str = "ytd",
) -> HTMLResponse:
    import dataclasses as _dc

    _accounts = accounts or []
    plan_view, pos_by_sym = _build_plan_view_for_request(repo, pricing, _accounts, selected_tag, sort_key)

    page_size_norm = page_size if page_size in (10, 25, 50, 100) else 25
    page_norm = max(1, page)
    total_rows = len(plan_view.rows)
    total_pages = max(1, (total_rows + page_size_norm - 1) // page_size_norm)
    page_norm = min(page_norm, total_pages)
    start_idx = (page_norm - 1) * page_size_norm
    end_idx = start_idx + page_size_norm
    plan_view = _dc.replace(plan_view, rows=list(plan_view.rows)[start_idx:end_idx])

    change_states, watch_results = _compute_change_states(plan_view, pos_by_sym, repo)

    return request.app.state.templates.TemplateResponse(
        request,
        "_positions_view_plan.html",
        {
            "plan_view": plan_view,
            "selected_accounts": _accounts,
            "selected_account": _accounts[0] if len(_accounts) == 1 else "",
            "selected_period": selected_period,
            "watch_by_target_id": watch_results,
            "change_states": change_states,
            "pagination": {
                "page": page_norm,
                "page_size": page_size_norm,
                "total_pages": total_pages,
                "total_rows": total_rows,
                "page_size_options": (10, 25, 50, 100),
            },
        },
    )


@router.get("/positions/plan/tags")
def plan_tags_autocomplete(
    repo: Repository = Depends(get_repository),
) -> JSONResponse:
    """Union of tags currently in use, alpha-sorted. Powers the chips
    autocomplete in the modal and the inline `+` popover."""
    return JSONResponse({"tags": list(repo.list_all_tags())})


@router.get("/positions/plan/modal", response_class=HTMLResponse)
def plan_modal(
    request: Request,
    symbol: str | None = None,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    target = repo.get_target(symbol) if symbol else None
    return request.app.state.templates.TemplateResponse(
        request,
        "_positions_plan_modal.html",
        {"_target": target, "error": None, "all_tags": list(repo.list_all_tags())},
    )


@router.post("/positions/plan/target", response_class=HTMLResponse)
async def plan_target_upsert(
    request: Request,
    symbol: str = Form(""),
    target_unit: str = Form("usd"),
    target_amount: str = Form("0"),
    tags: str | None = Form(default=None),
    repo: Repository = Depends(get_repository),
    pricing: PricingService = Depends(get_pricing_service),
) -> HTMLResponse:
    sym = (symbol or "").strip().upper()
    if not sym:
        return _modal_error(request, "Symbol is required.", status=422)
    try:
        amount = Decimal(target_amount)
    except (InvalidOperation, ValueError):
        return _modal_error(request, "Amount must be a number.", status=422)
    if amount <= 0:
        return _modal_error(request, "Amount must be positive.", status=422)
    if target_unit not in ("usd", "shares"):
        return _modal_error(request, "Invalid target type.", status=422)

    repo.upsert_target(sym, amount, TargetUnit(target_unit))

    # Tags semantics:
    #   - "tags" key absent from form   → leave existing tags untouched.
    #   - "tags" key present, value ""  → user cleared all tags.
    #   - "tags" key present, non-empty → CSV; split on commas, normalize.
    # FastAPI coerces empty-string form values to None for `str | None`,
    # so we read raw form data to distinguish "omitted" from "cleared".
    form_data = await request.form()
    if "tags" in form_data:
        raw_tags: str = form_data.get("tags") or ""  # type: ignore[assignment]
        parts = [p.strip() for p in raw_tags.split(",")]
        repo.set_target_tags(sym, parts)

    state = await _plan_toolbar_state(request)
    return _render_plan_body(request, repo, pricing, **state)


@router.delete("/positions/plan/target/{symbol}", response_class=HTMLResponse)
async def plan_target_delete(
    request: Request,
    symbol: str,
    repo: Repository = Depends(get_repository),
    pricing: PricingService = Depends(get_pricing_service),
) -> HTMLResponse:
    repo.delete_target(symbol)
    state = await _plan_toolbar_state(request)
    return _render_plan_body(request, repo, pricing, **state)


@router.post("/positions/plan/mark-seen")
def plan_mark_seen(
    request: Request,
    repo: Repository = Depends(get_repository),
    pricing: PricingService = Depends(get_pricing_service),
) -> Response:
    """Persist the current Plan view as the new 'last seen' snapshot.

    Snapshot is always global (cross-account) — the `account` filter on
    GET routes does not apply here. The current Plan view is built with
    all positions, all targets, all watch results, then written in full.

    Returns 204 No Content; the toolbar button reloads the page after
    success.
    """
    from dataclasses import asdict

    from net_alpha.portfolio.plan_diff import SnapshotRow

    plan_view, pos_by_sym = _build_plan_view_for_request(
        repo, pricing, accounts=[], selected_tag=None, sort_key="manual"
    )
    watch_results = repo.watch_results_by_target()
    diff_rows = _build_plan_diff_rows(plan_view, pos_by_sym, watch_results)
    snapshot = [SnapshotRow(**asdict(r)) for r in diff_rows]

    now_iso = dt.datetime.now(dt.UTC).isoformat()
    repo.mark_plan_seen(snapshot, when=now_iso)
    return Response(status_code=204)


@router.post("/positions/plan/target/{symbol}/tag", response_class=HTMLResponse)
async def plan_target_tag_add(
    request: Request,
    symbol: str,
    tag: str = Form(""),
    repo: Repository = Depends(get_repository),
    pricing: PricingService = Depends(get_pricing_service),
) -> HTMLResponse:
    """Add a tag to a target. Returns the refreshed plan body for HTMX."""
    sym = symbol.upper()
    if repo.get_target(sym) is None:
        raise HTTPException(status_code=404, detail=f"No target for {sym}")
    if not repo.add_target_tag(sym, tag):
        raise HTTPException(status_code=422, detail="Invalid tag")
    state = await _plan_toolbar_state(request)
    return _render_plan_body(request, repo, pricing, **state)


@router.delete(
    "/positions/plan/target/{symbol}/tag/{tag}",
    response_class=HTMLResponse,
)
async def plan_target_tag_remove(
    request: Request,
    symbol: str,
    tag: str,
    repo: Repository = Depends(get_repository),
    pricing: PricingService = Depends(get_pricing_service),
) -> HTMLResponse:
    """Remove a tag from a target. Idempotent. Returns refreshed plan body."""
    repo.remove_target_tag(symbol, tag)
    state = await _plan_toolbar_state(request)
    return _render_plan_body(request, repo, pricing, **state)


@router.post("/positions/plan/reorder", response_class=HTMLResponse)
async def plan_target_reorder(
    request: Request,
    repo: Repository = Depends(get_repository),
    pricing: PricingService = Depends(get_pricing_service),
) -> HTMLResponse:
    """Persist a new manual ordering of Plan targets and re-render the body.

    Body: form-encoded, repeated `order` keys (e.g. order=AAPL&order=MSFT).
    Toolbar state (account, tag, page, page_size, period) is propagated
    via _plan_toolbar_state. Always re-renders in Manual mode regardless
    of the inbound sort param.
    """
    form_data = await request.form()
    raw_order = form_data.getlist("order")
    repo.set_target_order(raw_order)
    state = await _plan_toolbar_state(request)
    state["sort_key"] = "manual"
    return _render_plan_body(request, repo, pricing, **state)
