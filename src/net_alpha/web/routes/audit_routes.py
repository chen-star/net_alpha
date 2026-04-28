from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from net_alpha.audit import decode_metric_ref, provenance_for
from net_alpha.audit.reconciliation import per_lot_diffs, reconcile
from net_alpha.db.repository import Repository
from net_alpha.web.dependencies import get_repository

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
