from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.web.dependencies import get_repository

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
        ((t.proceeds or 0.0) - (t.cost_basis or 0.0)
         for t in trades if t.date.year == today.year and t.is_sell()),
        start=0.0,
    )
    disallowed_ytd = sum(
        (v.disallowed_loss for v in violations
         if v.loss_sale_date and v.loss_sale_date.year == today.year),
        start=0.0,
    )
    accounts = sorted({lot.account for lot in lots})
    last_trade = trades[-1] if trades else None

    return request.app.state.templates.TemplateResponse(
        request,
        "ticker.html",
        {
            "symbol": symbol,
            "trades": trades,
            "lots": lots,
            "violations": violations,
            "kpi_open_lots": len(lots),
            "kpi_open_basis": sum((lot.adjusted_basis for lot in lots), start=0.0),
            "kpi_realized_ytd": realized_ytd,
            "kpi_disallowed_ytd": disallowed_ytd,
            "kpi_accounts": accounts,
            "kpi_last_trade": last_trade,
        },
    )
