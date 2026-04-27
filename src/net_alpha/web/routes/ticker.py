from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.models.realized_gl import RealizedGLLot
from net_alpha.web.dependencies import get_repository
from net_alpha.web.format import display_action

router = APIRouter()


@router.get("/ticker/{symbol}", response_class=HTMLResponse)
def ticker_drilldown(
    symbol: str,
    request: Request,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    symbol = symbol.upper()
    trades = repo.get_trades_for_ticker(symbol)
    lots = repo.get_lots_for_ticker(symbol)
    violations = repo.get_violations_for_ticker(symbol)

    today = date.today()
    realized_ytd = sum(
        ((t.proceeds or 0.0) - (t.cost_basis or 0.0) for t in trades if t.date.year == today.year and t.is_sell()),
        start=0.0,
    )
    disallowed_ytd = sum(
        (v.disallowed_loss for v in violations if v.loss_sale_date and v.loss_sale_date.year == today.year),
        start=0.0,
    )
    accounts = sorted({lot.account for lot in lots})
    last_trade = trades[-1] if trades else None

    # Load G/L lots for this ticker across all accounts that have any
    gl_lots: list[RealizedGLLot] = []
    for account in repo.list_accounts():
        gl_lots.extend(repo.get_gl_lots_for_ticker(account.id, symbol))

    return request.app.state.templates.TemplateResponse(
        request,
        "ticker.html",
        {
            "symbol": symbol,
            "trades": trades,
            "lots": lots,
            "violations": violations,
            "gl_lots": gl_lots,
            "kpi_open_lots": len(lots),
            "kpi_open_basis": sum((lot.adjusted_basis for lot in lots), start=0.0),
            "kpi_realized_ytd": realized_ytd,
            "kpi_disallowed_ytd": disallowed_ytd,
            "kpi_accounts": accounts,
            "kpi_last_trade": last_trade,
            "display_action": display_action,
        },
    )


@router.get("/ticker/{symbol}/add-form", response_class=HTMLResponse)
def trade_add_form(
    request: Request,
    symbol: str,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    accounts = sorted({imp.account_display for imp in repo.list_imports()})
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
    request: Request, symbol: str, trade_id: str,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    t = _find_trade(repo, trade_id)
    if t is None or not t.is_manual:
        raise HTTPException(status_code=404, detail="manual trade not found")
    accounts = sorted({imp.account_display for imp in repo.list_imports()})
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
    request: Request, symbol: str, trade_id: str,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    t = _find_trade(repo, trade_id)
    if t is None or t.basis_source not in ("transfer_in", "transfer_out") or t.is_manual:
        raise HTTPException(status_code=404, detail="transfer row not found")
    return request.app.state.templates.TemplateResponse(
        request,
        "_trade_transfer_form.html",
        {
            "form_action": f"/trades/{trade_id}/edit-transfer",
            "trade": t,
        },
    )


@router.get("/ticker/{symbol}/delete-confirm/{trade_id}", response_class=HTMLResponse)
def trade_delete_confirm(
    request: Request, symbol: str, trade_id: str,
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
