from __future__ import annotations

import logging
from datetime import date as _date

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse

from net_alpha.audit import decode_metric_ref, provenance_for
from net_alpha.audit.reconciliation import per_lot_diffs, reconcile
from net_alpha.db.repository import Repository
from net_alpha.engine.recompute import recompute_all_violations
from net_alpha.engine.stitch import stitch_account
from net_alpha.web.dependencies import get_etf_pairs, get_repository

router = APIRouter()
log = logging.getLogger(__name__)


def _post_basis_save_recompute(repo: Repository, etf_pairs: dict) -> None:
    """Re-stitch every account and recompute wash-sale violations after a
    basis or date edit. Also invalidates the audit badge cache so the nav
    reflects the change."""
    for acct in repo.list_accounts():
        if acct.id is not None:
            stitch_account(repo, acct.id)
    recompute_all_violations(repo, etf_pairs)
    from net_alpha.audit._badge_cache import _cache

    _cache.invalidate()


@router.get("/provenance/{encoded}", response_class=HTMLResponse)
def provenance_modal(
    encoded: str,
    request: Request,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    """HTMX fragment: provenance trace for one MetricRef.

    Always returns 200; failures render an error block inside the modal so the
    rest of the page is unaffected.
    """
    try:
        ref = decode_metric_ref(encoded)
        trace = provenance_for(ref, repo)
    except Exception as e:  # noqa: BLE001 — defensive: never bubble to 5xx
        log.exception("provenance trace failed: %s", e)
        return request.app.state.templates.TemplateResponse(
            request,
            "_provenance_modal.html",
            {"trace": None, "error": str(e)},
        )
    return request.app.state.templates.TemplateResponse(
        request,
        "_provenance_modal.html",
        {"trace": trace, "error": None},
    )


@router.get("/reconciliation/{symbol}", response_class=HTMLResponse)
def reconciliation_strip(
    symbol: str,
    request: Request,
    account_id: int = Query(...),
    expanded: bool = Query(False),
    variant: str = Query("full"),  # "full" | "badge"
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    result = reconcile(symbol=symbol.upper(), account_id=account_id, repo=repo)
    if variant == "badge":
        return request.app.state.templates.TemplateResponse(
            request,
            "_reconciliation_badge.html",
            {"result": result},
        )
    diffs = per_lot_diffs(symbol=symbol.upper(), account_id=account_id, repo=repo) if expanded else []
    template = "_reconciliation_diff.html" if expanded else "_reconciliation_strip.html"
    return request.app.state.templates.TemplateResponse(
        request,
        template,
        {"result": result, "diffs": diffs},
    )


@router.post("/audit/set-basis", response_class=HTMLResponse)
def set_basis(
    request: Request,
    trade_id: str = Form(...),
    cost_basis: float = Form(...),
    caller: str | None = Query(None),
    repo: Repository = Depends(get_repository),
    etf_pairs: dict = Depends(get_etf_pairs),
) -> HTMLResponse:
    repo.update_trade_basis(
        trade_id=trade_id,
        cost_basis=cost_basis,
        basis_source="user_set",
    )
    # Re-stitch every account (cheap) so any sell with the now-set buy basis
    # gets correctly hydrated, then recompute wash-sale violations.
    _post_basis_save_recompute(repo, etf_pairs)
    if caller == "timeline":
        return HTMLResponse(
            f'<td class="px-2 py-1 num font-mono" id="trade-basis-{trade_id}">'
            f'${cost_basis:.2f} <span class="text-pos text-[11px] ml-1">✓ saved</span></td>'
        )
    if caller == "drawer":
        # Return a compact saved-row fragment for the Imports drawer inline form.
        return request.app.state.templates.TemplateResponse(
            request,
            "_data_hygiene_row_saved.html",
            {"trade_id": trade_id, "cost_basis": cost_basis},
        )
    elif caller == "pane":
        # Return an inline confirmation that stays inside the positions pane.
        trade = repo.get_trade_by_id(int(trade_id))
        sym = trade.ticker if trade is not None else ""
        return request.app.state.templates.TemplateResponse(
            request,
            "_positions_pane_set_basis_saved.html",
            {"sym": sym},
        )
    return request.app.state.templates.TemplateResponse(
        request,
        "_data_hygiene_set_basis.html",
        {"trade_id": trade_id, "cost_basis": cost_basis},
    )


@router.post("/audit/set-basis/single", response_class=HTMLResponse)
def set_basis_single(
    request: Request,
    trade_id: str = Form(...),
    cost_basis: float = Form(...),
    acquisition_date: str = Form(...),
    caller: str | None = Query(None),
    repo: Repository = Depends(get_repository),
    etf_pairs: dict = Depends(get_etf_pairs),
) -> HTMLResponse:
    """Single-lot inline save: cost_basis + acquisition_date on one transfer row."""
    if cost_basis < 0:
        return HTMLResponse(
            '<div class="text-neg text-[12px]">Cost basis must be ≥ 0.</div>',
            status_code=400,
        )

    try:
        acq_date = _date.fromisoformat(acquisition_date)
    except ValueError:
        return HTMLResponse(
            '<div class="text-neg text-[12px]">Invalid date format. Use YYYY-MM-DD.</div>',
            status_code=400,
        )

    today = _date.today()
    if acq_date > today:
        return HTMLResponse(
            '<div class="text-neg text-[12px]">Acquisition date cannot be in the future.</div>',
            status_code=400,
        )

    try:
        parsed_id = int(trade_id)
    except ValueError:
        return HTMLResponse(
            '<div class="text-neg text-[12px]">Invalid trade id.</div>',
            status_code=400,
        )

    trade = repo.get_trade_by_id(parsed_id)
    if trade is None:
        return HTMLResponse(
            '<div class="text-neg text-[12px]">Trade not found.</div>',
            status_code=404,
        )

    if acq_date > trade.date:
        xfer_iso = trade.date.isoformat()
        return HTMLResponse(
            f'<div class="text-neg text-[12px]">Acquisition date must be before transfer date ({xfer_iso}).</div>',
            status_code=400,
        )

    repo.update_trade_basis(
        trade_id=trade_id,
        cost_basis=cost_basis,
        basis_source="user_set",
        trade_date=acq_date,
    )
    _post_basis_save_recompute(repo, etf_pairs)

    if caller == "pane":
        return request.app.state.templates.TemplateResponse(
            request,
            "_positions_pane_set_basis_saved.html",
            {"sym": trade.ticker},
        )
    return HTMLResponse('<div class="text-pos text-[12px]">Saved.</div>')


@router.get("/audit/set-basis/multi/{trade_id}", response_class=HTMLResponse)
def set_basis_multi_fragment(
    trade_id: str,
    request: Request,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    """HTMX swap target: render the multi-lot row-table fragment for one
    transfer-in trade.

    When the trade is part of an existing transfer_group (i.e. the user has
    already split it once), the fragment shows the FULL original group
    quantity and pre-fills one row per existing sibling so the user can edit
    each lot's basis in place instead of being locked into the parent's
    current segment quantity.
    """
    try:
        parsed_id = int(trade_id)
    except ValueError:
        return HTMLResponse(
            '<div class="text-neg text-[12px]">Invalid trade id.</div>',
            status_code=400,
        )
    trade = repo.get_trade_by_id(parsed_id)
    if trade is None or trade.basis_source != "transfer_in":
        return HTMLResponse(
            '<div class="text-neg text-[12px]">Not a transfer-in trade.</div>',
            status_code=400,
        )

    siblings = repo.get_trades_in_transfer_group(trade.transfer_group_id) if trade.transfer_group_id else []
    if siblings:
        transfer_qty = sum(s.quantity for s in siblings)
        existing_segments = [
            {
                "date": s.date.isoformat(),
                "quantity": s.quantity,
                "basis": s.cost_basis if s.cost_basis is not None else "",
            }
            for s in siblings
        ]
    else:
        transfer_qty = trade.quantity
        existing_segments = []

    return request.app.state.templates.TemplateResponse(
        request,
        "_positions_pane_set_basis_multi.html",
        {
            "trade_id": trade_id,
            "sym": trade.ticker,
            "transfer_qty": transfer_qty,
            "transfer_date": trade.transfer_date or trade.date,
            "existing_segments": existing_segments,
        },
    )


@router.get("/audit/set-basis/single/{trade_id}", response_class=HTMLResponse)
def set_basis_single_fragment(
    trade_id: str,
    request: Request,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    """HTMX swap target: render the single-lot fragment (used by the
    "Back to single lot" link in the multi-lot fragment)."""
    try:
        parsed_id = int(trade_id)
    except ValueError:
        return HTMLResponse(
            '<div class="text-neg text-[12px]">Invalid trade id.</div>',
            status_code=400,
        )
    trade = repo.get_trade_by_id(parsed_id)
    if trade is None:
        return HTMLResponse(
            '<div class="text-neg text-[12px]">Trade not found.</div>',
            status_code=404,
        )
    return request.app.state.templates.TemplateResponse(
        request,
        "_positions_pane_set_basis.html",
        {
            "trade_id": trade_id,
            "sym": trade.ticker,
            "transfer_qty": trade.quantity,
            "transfer_date": trade.date,
        },
    )


@router.post("/audit/set-basis/multi", response_class=HTMLResponse)
def set_basis_multi(
    request: Request,
    trade_id: str = Form(...),
    dates: list[str] = Form(...),
    quantities: list[float] = Form(...),
    basises: list[float] = Form(...),
    caller: str | None = Query(None),
    repo: Repository = Depends(get_repository),
    etf_pairs: dict = Depends(get_etf_pairs),
) -> HTMLResponse:
    """Multi-lot inline save: split one transfer row into N siblings."""
    if not (len(dates) == len(quantities) == len(basises)):
        return HTMLResponse(
            '<div class="text-neg text-[12px]">Mismatched row counts.</div>',
            status_code=400,
        )
    if len(dates) < 1:
        return HTMLResponse(
            '<div class="text-neg text-[12px]">At least one lot is required.</div>',
            status_code=400,
        )

    try:
        parsed_id = int(trade_id)
    except ValueError:
        return HTMLResponse(
            '<div class="text-neg text-[12px]">Invalid trade id.</div>',
            status_code=400,
        )

    trade = repo.get_trade_by_id(parsed_id)
    if trade is None or trade.basis_source != "transfer_in":
        return HTMLResponse(
            '<div class="text-neg text-[12px]">Not a transfer-in trade.</div>',
            status_code=400,
        )

    # The constraint upper bound for acquisition dates and the qty-sum target
    # is the ORIGINAL transfer (preserved on transfer_date and across all
    # siblings), not whatever the parent row currently holds after a prior
    # split. Falling back to trade.date covers transfers that pre-date the
    # transfer_date column.
    xfer_date = trade.transfer_date or trade.date
    siblings = repo.get_trades_in_transfer_group(trade.transfer_group_id) if trade.transfer_group_id else []
    expected_total_qty = sum(s.quantity for s in siblings) if siblings else trade.quantity

    today = _date.today()
    parsed: list[tuple[_date, float, float]] = []
    for d_str, q, b in zip(dates, quantities, basises, strict=False):
        try:
            d = _date.fromisoformat(d_str)
        except ValueError:
            return HTMLResponse(
                '<div class="text-neg text-[12px]">Invalid date format. Use YYYY-MM-DD.</div>',
                status_code=400,
            )
        if d > today:
            return HTMLResponse(
                '<div class="text-neg text-[12px]">Acquisition dates cannot be in the future.</div>',
                status_code=400,
            )
        if d > xfer_date:
            msg = (
                f'<div class="text-neg text-[12px]">Acquisition date {d.isoformat()}'
                f" is after transfer date {xfer_date.isoformat()}.</div>"
            )
            return HTMLResponse(msg, status_code=400)
        if q <= 0:
            return HTMLResponse(
                '<div class="text-neg text-[12px]">Quantities must be > 0.</div>',
                status_code=400,
            )
        if b < 0:
            return HTMLResponse(
                '<div class="text-neg text-[12px]">Cost basis must be ≥ 0.</div>',
                status_code=400,
            )
        parsed.append((d, q, b))

    qty_sum = sum(q for _, q, _ in parsed)
    if abs(qty_sum - expected_total_qty) > 1e-4:
        msg = (
            f'<div class="text-neg text-[12px]">Quantities sum to {qty_sum}'
            f" but transferred quantity is {expected_total_qty}.</div>"
        )
        return HTMLResponse(msg, status_code=400)

    repo.split_imported_transfer(trade_id=trade_id, segments=parsed, etf_pairs=etf_pairs)

    # split_imported_transfer already calls recompute_all_violations internally,
    # so we don't double-call it. We do still need to invalidate the badge cache.
    from net_alpha.audit._badge_cache import _cache

    _cache.invalidate()

    if caller == "pane":
        return request.app.state.templates.TemplateResponse(
            request,
            "_positions_pane_set_basis_saved.html",
            {"sym": trade.ticker},
        )
    return HTMLResponse('<div class="text-pos text-[12px]">Saved.</div>')
