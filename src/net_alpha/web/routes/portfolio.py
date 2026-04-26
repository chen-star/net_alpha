from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.portfolio.equity_curve import build_equity_curve
from net_alpha.portfolio.lot_aging import top_lots_crossing_ltcg
from net_alpha.portfolio.pnl import compute_kpis, compute_wash_impact
from net_alpha.portfolio.positions import compute_open_positions
from net_alpha.portfolio.treemap import build_treemap
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
    repo: Repository = Depends(get_repository),
) -> dict[str, object]:
    if not symbols:
        raise HTTPException(status_code=400, detail="symbols query param required")
    if symbols.strip().upper() == "ALL":
        sym_list = sorted({lot.ticker for lot in repo.all_lots() if lot.option_details is None})
    else:
        sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not sym_list:
        # Nothing to refresh (no open lots, or empty list)
        return {"fetched": [], "missing": [], "degraded": False}
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


@router.get("/portfolio/treemap", response_class=HTMLResponse)
def portfolio_treemap(
    request: Request,
    account: str | None = None,
    repo: Repository = Depends(get_repository),
    svc: PricingService = Depends(get_pricing_service),
) -> HTMLResponse:
    today = date.today()
    trades = repo.all_trades()
    lots = repo.all_lots()
    symbols = sorted({lot.ticker for lot in lots if lot.option_details is None})
    prices = svc.get_prices(symbols)
    rows = compute_open_positions(
        trades=trades,
        lots=lots,
        prices=prices,
        period=(today.year, today.year + 1),
        account=account or None,
    )
    tiles = build_treemap(positions=rows, top_n=8)
    return request.app.state.templates.TemplateResponse(
        request,
        "_portfolio_treemap.html",
        {"tiles": tiles},
    )


@router.get("/portfolio/equity-curve", response_class=HTMLResponse)
def portfolio_equity_curve(
    request: Request,
    period: str | None = None,
    account: str | None = None,
    repo: Repository = Depends(get_repository),
    svc: PricingService = Depends(get_pricing_service),
) -> HTMLResponse:
    today = date.today()
    period_tuple, period_label = _parse_period(period, today.year)
    year = period_tuple[0] if period_tuple else today.year
    trades = repo.all_trades()
    if account:
        trades = [t for t in trades if t.account == account]
    lots = repo.all_lots()
    if account:
        lots = [lot for lot in lots if lot.account == account]
    symbols = sorted({lot.ticker for lot in lots if lot.option_details is None})
    prices = svc.get_prices(symbols)
    kpis = compute_kpis(
        trades=trades,
        lots=lots,
        prices=prices,
        period_label=period_label,
        period=period_tuple,
        account=None,  # already filtered
    )
    points = build_equity_curve(trades=trades, year=year, present_unrealized=kpis.period_unrealized)
    return request.app.state.templates.TemplateResponse(
        request,
        "_portfolio_equity_curve.html",
        {"points": points, "year": year},
    )


@router.get("/portfolio/wash-impact", response_class=HTMLResponse)
def portfolio_wash_impact(
    request: Request,
    period: str | None = None,
    account: str | None = None,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    today = date.today()
    period_tuple, period_label = _parse_period(period, today.year)
    impact = compute_wash_impact(
        violations=repo.all_violations(),
        period_label=period_label,
        period=period_tuple,
        account=account or None,
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "_portfolio_wash_impact.html",
        {"impact": impact},
    )


@router.get("/portfolio/lot-aging", response_class=HTMLResponse)
def portfolio_lot_aging(
    request: Request,
    account: str | None = None,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    lots = repo.all_lots()
    if account:
        lots = [lot for lot in lots if lot.account == account]
    aging = top_lots_crossing_ltcg(lots=lots, horizon_days=90, top_n=5)
    return request.app.state.templates.TemplateResponse(
        request,
        "_portfolio_lot_aging.html",
        {"aging": aging},
    )
