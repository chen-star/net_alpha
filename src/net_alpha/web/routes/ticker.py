from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from datetime import date as _date

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from net_alpha.audit import Period, RealizedPLRef
from net_alpha.db.repository import Repository
from net_alpha.models.domain import OptionDetails, Trade
from net_alpha.models.realized_gl import RealizedGLLot
from net_alpha.portfolio.pnl import realized_pl_from_trades
from net_alpha.portfolio.positions import compute_open_short_option_positions, open_lots_view
from net_alpha.web.dependencies import get_repository
from net_alpha.web.format import display_action

router = APIRouter()

PAGE_SIZE = 25
PAGE_SIZE_OPTIONS = (10, 25, 50, 100)


@dataclass(frozen=True)
class TimelineRow:
    """Display-ready Timeline entry — either a real Trade or a synthetic
    closure (option expiry from Schwab GL with no matching BTC trade).

    ``gain_loss`` is the realized P&L attributable to *this* row, when the row
    represents a close. None for opening events (BTO long, STO short) and for
    transfers / non-realizing actions. Closing rows get:

    - **Long-lot Sell** (equity sale, STC of long option): ``proceeds - cost_basis``.
    - **BTC of short** (option_short_close, _expiry, _assigned synthetic): the
      paired STO premium minus the BTC cost. Assigned-close folds into the
      stock buy basis instead and is intentionally ``None`` here so the user
      sees the realization only on the eventual stock sale.
    """

    trade: Trade
    assigned_from: OptionDetails | None = None  # set on put_assignment Buy rows
    gain_loss: float | None = None


def _build_timeline_rows(
    trades: list[Trade],
    gl_lots: list[RealizedGLLot],
) -> list[TimelineRow]:
    """Assemble the ticker-page Timeline rows.

    Two transformations vs the raw trade list:

    1. Synthesise a "Closed by Expiry" row for each option GL lot whose
       underlying STO has no matching BTC trade and is not already
       represented by a synthetic ``option_short_close_assigned`` Buy.
       Without this, a Sell-to-Open that simply expired worthless would
       leave the user wondering whether the position is still open.

    2. Drop ``option_short_close_assigned`` rows; their information is
       folded into the paired ``put_assignment`` Buy via ``assigned_from``
       so a single timeline entry tells the full assignment story.
    """
    # --- Index assigned-close trades by (date, account, ticker) ---
    assigned_close_by_key: dict[tuple[date, str, str], OptionDetails] = {}
    for t in trades:
        if t.basis_source == "option_short_close_assigned" and t.option_details is not None:
            assigned_close_by_key[(t.date, t.account, t.ticker)] = t.option_details

    # --- Index BTC / STC trade closures so we don't duplicate via GL ---
    closed_keys_in_trades: set[tuple[str, float, date, str]] = set()
    for t in trades:
        if t.option_details is None:
            continue
        if t.action.lower() != "buy":
            continue  # only closes on the buy side (BTC, including assigned-close)
        opt = t.option_details
        closed_keys_in_trades.add((t.ticker, opt.strike, opt.expiry, opt.call_put))

    # --- Index STO premium per (account, ticker, strike, expiry, cp) so each
    # BTC row can show the close-event gain/loss. We accept multiple STOs
    # (e.g. an STO that was rolled and then closed in one BTC).
    sto_premium_by_key: dict[tuple[str, str, float, date, str], float] = {}
    for t in trades:
        if not t.is_sell() or not t.basis_source.startswith("option_short_open"):
            continue
        if t.option_details is None:
            continue
        opt = t.option_details
        key = (t.account, t.ticker, opt.strike, opt.expiry, opt.call_put)
        sto_premium_by_key[key] = sto_premium_by_key.get(key, 0.0) + (t.proceeds or 0.0)

    def _row_gain_loss(t: Trade) -> float | None:
        # Long-lot Sells (equity sale, STC of long option): direct realization.
        if t.is_sell():
            if t.basis_source.startswith("option_short_open"):
                return None  # opening event, no realization yet
            if t.proceeds is None or t.cost_basis is None:
                return None
            return float(t.proceeds) - float(t.cost_basis)
        # BTC of regular / expired short: STO_premium - BTC_cost.
        if t.is_buy() and t.basis_source in {"option_short_close", "option_short_close_expiry"}:
            if t.option_details is None:
                return None
            opt = t.option_details
            key = (t.account, t.ticker, opt.strike, opt.expiry, opt.call_put)
            sto = sto_premium_by_key.get(key, 0.0)
            return sto - float(t.cost_basis or 0.0)
        return None

    rows: list[TimelineRow] = []
    for t in trades:
        if t.basis_source == "option_short_close_assigned":
            continue  # folded into the put-assignment Buy via assigned_from
        assigned_from = None
        if t.basis_source == "put_assignment":
            assigned_from = assigned_close_by_key.get((t.date, t.account, t.ticker))
        rows.append(TimelineRow(trade=t, assigned_from=assigned_from, gain_loss=_row_gain_loss(t)))

    # --- Synthesize Closed-by-Expiry rows from GL ---
    seen_synth: set[tuple[str, float, date, str, date]] = set()
    for gl in gl_lots:
        if gl.option_strike is None or gl.option_expiry is None or gl.option_call_put is None:
            continue
        try:
            expiry = date.fromisoformat(gl.option_expiry)
        except ValueError:
            continue
        key = (gl.ticker, float(gl.option_strike), expiry, gl.option_call_put)
        if key in closed_keys_in_trades:
            continue  # already represented by a BTC / STC / assigned-close trade
        synth_key = (gl.ticker, float(gl.option_strike), expiry, gl.option_call_put, gl.closed_date)
        if synth_key in seen_synth:
            continue
        seen_synth.add(synth_key)
        synth = Trade(
            account=gl.account_display,
            date=gl.closed_date,
            ticker=gl.ticker,
            action="Buy",  # closing a short = buy-side
            quantity=abs(float(gl.quantity)),
            cost_basis=float(gl.cost_basis),
            proceeds=None,
            basis_source="option_short_close_expiry",
            option_details=OptionDetails(
                strike=float(gl.option_strike),
                expiry=expiry,
                call_put=gl.option_call_put,
            ),
        )
        rows.append(TimelineRow(trade=synth, gain_loss=_row_gain_loss(synth)))

    rows.sort(key=lambda r: (r.trade.date, r.trade.id))
    return rows


@router.get("/ticker/{symbol}", response_class=HTMLResponse)
def ticker_drilldown(
    symbol: str,
    request: Request,
    view: str = Query("timeline"),
    page: int = Query(1, ge=1),
    page_size: int = Query(PAGE_SIZE),
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    symbol = symbol.upper()
    if view not in {"timeline", "lots", "recon"}:
        view = "timeline"
    if page_size not in PAGE_SIZE_OPTIONS:
        page_size = PAGE_SIZE
    trades = repo.get_trades_for_ticker(symbol)
    raw_lots = repo.get_lots_for_ticker(symbol)
    # Filter to lots that are still open after consuming sells / GL closures.
    # Without this, a BTO that expired worthless (only Schwab GL records the
    # close) appears in the "Open lots" table forever.
    lots = open_lots_view(
        lots=raw_lots,
        trades=repo.all_trades(),
        gl_closures=repo.get_equity_gl_closures(),
        gl_option_closures=repo.get_option_gl_closures(),
    )
    open_shorts = compute_open_short_option_positions(
        repo.all_trades(),
        ticker=symbol,
        gl_option_closures=repo.get_option_gl_closures(),
    )
    violations = repo.get_violations_for_ticker(symbol)

    # Load G/L lots for this ticker across all accounts. Used both to feed
    # realized P&L (so long-option expirations dropped by the parser still
    # land in YTD/lifetime) and to synthesize Closed-by-Expiry timeline rows.
    gl_lots: list[RealizedGLLot] = []
    for account in repo.list_accounts():
        gl_lots.extend(repo.get_gl_lots_for_ticker(account.id, symbol))

    today = date.today()
    realized_ytd = float(
        realized_pl_from_trades(trades, period=(today.year, today.year + 1), gl_lots=gl_lots)
    )
    realized_lifetime = float(realized_pl_from_trades(trades, period=None, gl_lots=gl_lots))
    disallowed_ytd = sum(
        (v.disallowed_loss for v in violations if v.loss_sale_date and v.loss_sale_date.year == today.year),
        start=0.0,
    )
    disallowed_lifetime = sum(
        (v.disallowed_loss for v in violations),
        start=0.0,
    )
    # Union trade accounts with lot accounts so the KPI strip still surfaces
    # accounts when only short options are open (no long lots → empty `lots`).
    accounts = sorted({t.account for t in trades} | {lot.account for lot in lots})
    last_trade = trades[-1] if trades else None

    # Use all accounts that have any trade for this symbol (not just open lots,
    # so the strip appears even when all lots have been closed or not yet built).
    trade_displays = {t.account for t in trades}
    account_ids: list[int] = []
    for a in repo.list_accounts():
        display = f"{a.broker}/{a.label}" if a.label else a.broker
        if display in trade_displays and a.id is not None:
            account_ids.append(a.id)
    account_ids.sort()

    timeline_rows = _build_timeline_rows(list(trades), gl_lots)

    # Independent pagination for the Timeline and Open-lots tabs. Each tab
    # uses a single shared `page` query param; switching tabs (full <a> nav
    # without ?page=) implicitly resets to page 1.
    if view == "timeline":
        timeline_total = len(timeline_rows)
        timeline_total_pages = max(1, (timeline_total + page_size - 1) // page_size)
        timeline_page = max(1, min(page, timeline_total_pages))
        t_start = (timeline_page - 1) * page_size
        timeline_rows_page = timeline_rows[t_start : t_start + page_size]
        lots_page = lots
        lots_total = len(lots)
        lots_total_pages = max(1, (lots_total + page_size - 1) // page_size)
        lots_page_num = 1
    elif view == "lots":
        lots_total = len(lots)
        lots_total_pages = max(1, (lots_total + page_size - 1) // page_size)
        lots_page_num = max(1, min(page, lots_total_pages))
        l_start = (lots_page_num - 1) * page_size
        lots_page = lots[l_start : l_start + page_size]
        timeline_rows_page = timeline_rows
        timeline_total = len(timeline_rows)
        timeline_total_pages = max(1, (timeline_total + page_size - 1) // page_size)
        timeline_page = 1
    else:
        timeline_rows_page = timeline_rows
        lots_page = lots
        timeline_total = len(timeline_rows)
        lots_total = len(lots)
        timeline_total_pages = max(1, (timeline_total + page_size - 1) // page_size)
        lots_total_pages = max(1, (lots_total + page_size - 1) // page_size)
        timeline_page = 1
        lots_page_num = 1

    realized_ref = RealizedPLRef(
        kind="realized_pl",
        period=Period(
            start=_date(today.year, 1, 1),
            end=_date(today.year + 1, 1, 1),
            label=f"YTD {today.year}",
        ),
        account_id=None,  # ticker page is account-aggregated
        symbol=symbol,
    )
    realized_lifetime_ref = RealizedPLRef(
        kind="realized_pl",
        period=Period(start=_date(1970, 1, 1), end=_date(2100, 1, 1), label="Lifetime"),
        account_id=None,
        symbol=symbol,
    )

    ctx = {
        "symbol": symbol,
        "trades": trades,
        "timeline_rows": timeline_rows_page,
        "lots": lots_page,
        "open_shorts": open_shorts,
        "timeline_page": timeline_page,
        "timeline_total_pages": timeline_total_pages,
        "timeline_total_count": timeline_total,
        "lots_page": lots_page_num,
        "lots_total_pages": lots_total_pages,
        "lots_total_count": lots_total,
        "page_size": page_size,
        "page_size_options": PAGE_SIZE_OPTIONS,
        "kpi_today": today,
        "violations": violations,
        "gl_lots": gl_lots,
        "kpi_open_lots": len(lots),
        "kpi_open_basis": sum((lot.adjusted_basis for lot in lots), start=0.0),
        "kpi_realized_ytd": realized_ytd,
        "kpi_realized_lifetime": realized_lifetime,
        "kpi_disallowed_ytd": disallowed_ytd,
        "kpi_disallowed_lifetime": disallowed_lifetime,
        "realized_lifetime_ref": realized_lifetime_ref,
        "kpi_accounts": accounts,
        "kpi_last_trade": last_trade,
        "account_ids": account_ids,
        "display_action": display_action,
        "realized_ref": realized_ref,
        "selected_view": view,
    }
    if request.headers.get("HX-Request") == "true":
        fragment_template = {
            "timeline": "_ticker_view_timeline.html",
            "lots": "_ticker_view_lots.html",
            "recon": "_ticker_view_reconciliation.html",
        }[view]
        return request.app.state.templates.TemplateResponse(request, fragment_template, ctx)
    return request.app.state.templates.TemplateResponse(request, "ticker.html", ctx)


@router.post("/lots/{lot_id}/edit", response_class=HTMLResponse)
def edit_lot(
    lot_id: int,
    request: Request,
    quantity: float = Form(...),
    adjusted_basis: float = Form(...),
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    from net_alpha.engine.recompute import recompute_all_violations

    lot = repo.get_lot_row_dict_by_id(lot_id)
    if lot is None:
        raise HTTPException(status_code=404, detail=f"Lot {lot_id} not found")
    old_qty = lot["quantity"]
    old_basis = lot["adjusted_basis"]
    trade_id = lot["trade_id"]

    # Persist the override audit BEFORE the lot mutation so the recompute
    # below picks it up on the way back through.
    if old_qty != quantity:
        repo.add_lot_override(
            trade_id=int(trade_id),
            field="quantity",
            old_value=old_qty,
            new_value=quantity,
            reason="manual",
        )
    if old_basis != adjusted_basis:
        repo.add_lot_override(
            trade_id=int(trade_id),
            field="adjusted_basis",
            old_value=old_basis,
            new_value=adjusted_basis,
            reason="manual",
        )

    # Trigger a full recompute. apply_manual_overrides will replay our edit.
    recompute_all_violations(repo, request.app.state.etf_pairs)

    # Return 204 No Content; client reloads via @htmx:after-request handler.
    return HTMLResponse(status_code=204)


@router.get("/ticker/{symbol}/add-form", response_class=HTMLResponse)
def trade_add_form(
    request: Request,
    symbol: str,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    accounts = sorted({f"{a.broker}/{a.label}" for a in repo.list_accounts()})
    return request.app.state.templates.TemplateResponse(
        request,
        "_trade_form.html",
        {
            "form_action": "/trades",
            "accounts": accounts,
            "submit_label": "Add trade",
            "trade": None,
            "symbol": symbol.upper(),
        },
    )


def _find_trade(repo: Repository, trade_id: str):
    for t in repo.all_trades():
        if t.id == trade_id:
            return t
    return None


@router.get("/ticker/{symbol}/edit-manual-form/{trade_id}", response_class=HTMLResponse)
def trade_edit_manual_form(
    request: Request,
    symbol: str,
    trade_id: str,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    t = _find_trade(repo, trade_id)
    if t is None or not t.is_manual:
        raise HTTPException(status_code=404, detail="manual trade not found")
    accounts = sorted({f"{a.broker}/{a.label}" for a in repo.list_accounts()})
    return request.app.state.templates.TemplateResponse(
        request,
        "_trade_form.html",
        {
            "form_action": f"/trades/{trade_id}/edit-manual",
            "accounts": accounts,
            "submit_label": "Save changes",
            "trade": t,
            "symbol": symbol.upper(),
        },
    )


@router.get("/ticker/{symbol}/edit-transfer-form/{trade_id}", response_class=HTMLResponse)
def trade_edit_transfer_form(
    request: Request,
    symbol: str,
    trade_id: str,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    t = _find_trade(repo, trade_id)
    if t is None or t.basis_source not in ("transfer_in", "transfer_out") or t.is_manual:
        raise HTTPException(status_code=404, detail="transfer row not found")
    # When this transfer was previously split, surface every sibling so the
    # form re-opens with all segments populated. Sorted by acquisition date
    # for predictable ordering.
    siblings: list[Trade] = []
    if t.transfer_group_id:
        siblings = sorted(
            (x for x in repo.all_trades() if x.transfer_group_id == t.transfer_group_id),
            key=lambda x: x.date,
        )
    return request.app.state.templates.TemplateResponse(
        request,
        "_trade_transfer_form.html",
        {
            "form_action": f"/trades/{trade_id}/edit-transfer",
            "trade": t,
            "siblings": siblings,
        },
    )


@router.get("/ticker/{symbol}/delete-confirm/{trade_id}", response_class=HTMLResponse)
def trade_delete_confirm(
    request: Request,
    symbol: str,
    trade_id: str,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    t = _find_trade(repo, trade_id)
    if t is None or not t.is_manual:
        raise HTTPException(status_code=404, detail="manual trade not found")
    return request.app.state.templates.TemplateResponse(
        request,
        "_trade_delete_confirm.html",
        {
            "form_action": f"/trades/{trade_id}/delete",
            "trade": t,
        },
    )
