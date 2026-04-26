from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.portfolio.pnl import compute_kpis
from net_alpha.portfolio.positions import compute_open_positions
from net_alpha.pricing.service import PricingService
from net_alpha.web.dependencies import get_pricing_service, get_repository

router = APIRouter()


def _parse_period(period: str | None, current_year: int) -> tuple[tuple[int, int] | None, str]:
    """Return ((start, end_exclusive) | None, label)."""
    if not period or period == "ytd":
        return ((current_year, current_year + 1), f"YTD {current_year}")
    if period == "lifetime":
        return (None, "Lifetime")
    try:
        y = int(period)
        return ((y, y + 1), str(y))
    except ValueError:
        return ((current_year, current_year + 1), f"YTD {current_year}")


@router.post("/prices/refresh")
def refresh_prices(
    symbols: str | None = Query(default=None),
    svc: PricingService = Depends(get_pricing_service),
) -> dict[str, object]:
    if not symbols:
        raise HTTPException(status_code=400, detail="symbols query param required")
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not sym_list:
        raise HTTPException(status_code=400, detail="symbols query param required")
    quotes = svc.refresh(sym_list)
    snap = svc.last_snapshot()
    return {
        "fetched": list(quotes.keys()),
        "missing": snap.missing_symbols,
        "degraded": snap.degraded,
    }


@router.get("/", response_class=HTMLResponse)
def portfolio_page(
    request: Request,
    period: str | None = None,
    account: str | None = None,
    group_options: str = "merge",
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    imports = repo.list_imports()
    accounts = sorted({imp.account_display for imp in imports})

    today = date.today()
    current_year = today.year
    import_years = {imp.imported_at.year for imp in imports}
    available_years = sorted(import_years | {current_year}, reverse=True)

    selected_period = period or "ytd"
    return request.app.state.templates.TemplateResponse(
        request,
        "portfolio.html",
        {
            "imports": imports,
            "accounts": accounts,
            "available_years": available_years,
            "current_year": current_year,
            "selected_period": selected_period,
            "selected_account": account or "",
            "group_options": group_options,
        },
    )


@router.get("/portfolio/kpis", response_class=HTMLResponse)
def portfolio_kpis(
    request: Request,
    period: str | None = None,
    account: str | None = None,
    repo: Repository = Depends(get_repository),
    svc: PricingService = Depends(get_pricing_service),
) -> HTMLResponse:
    today = date.today()
    period_tuple, period_label = _parse_period(period, today.year)
    trades = repo.all_trades()
    lots = repo.all_lots()
    symbols = sorted({lot.ticker for lot in lots if lot.option_details is None})
    prices = svc.get_prices(symbols)
    kpis = compute_kpis(
        trades=trades,
        lots=lots,
        prices=prices,
        period_label=period_label,
        period=period_tuple,
        account=account or None,
    )
    snap = svc.last_snapshot()
    return request.app.state.templates.TemplateResponse(
        request,
        "_portfolio_kpis.html",
        {"kpis": kpis, "snapshot": snap},
    )


@router.get("/portfolio/positions", response_class=HTMLResponse)
def portfolio_positions(
    request: Request,
    period: str | None = None,
    account: str | None = None,
    group_options: str = "merge",
    repo: Repository = Depends(get_repository),
    svc: PricingService = Depends(get_pricing_service),
) -> HTMLResponse:
    today = date.today()
    period_tuple, period_label = _parse_period(period, today.year)
    trades = repo.all_trades()
    lots = repo.all_lots()
    symbols = sorted({lot.ticker for lot in lots if lot.option_details is None})
    prices = svc.get_prices(symbols)
    rows = compute_open_positions(
        trades=trades,
        lots=lots,
        prices=prices,
        period=period_tuple,
        account=account or None,
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "_portfolio_table.html",
        {"rows": rows, "period_label": period_label},
    )
