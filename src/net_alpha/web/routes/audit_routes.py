from __future__ import annotations

import logging

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
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    result = reconcile(symbol=symbol.upper(), account_id=account_id, repo=repo)
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
    for acct in repo.list_accounts():
        if acct.id is not None:
            stitch_account(repo, acct.id)
    recompute_all_violations(repo, etf_pairs)
    # Invalidate the badge cache so the nav updates after the fix.
    from net_alpha.audit._badge_cache import _cache

    _cache.invalidate()
    return request.app.state.templates.TemplateResponse(
        request,
        "_data_hygiene_set_basis.html",
        {"trade_id": trade_id, "cost_basis": cost_basis},
    )
