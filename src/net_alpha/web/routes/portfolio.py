from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.portfolio.allocation import build_allocation
from net_alpha.portfolio.equity_curve import build_equity_curve
from net_alpha.portfolio.pnl import compute_kpis, compute_wash_impact
from net_alpha.portfolio.positions import compute_open_positions
from net_alpha.portfolio.wash_watch import recent_loss_closes
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


@router.post("/splits/sync")
def sync_splits(
    symbols: str | None = Query(default="ALL"),
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
        return {"applied_count": 0, "skipped_count": 0, "error_symbols": []}
    result = svc.sync_splits(sym_list, repo=repo)
    return {
        "applied_count": result.applied_count,
        "skipped_count": result.skipped_count,
        "error_symbols": result.error_symbols,
    }


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
            "toolbar_action": "/",
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
    wi = compute_wash_impact(
        violations=repo.all_violations(),
        period_label=period_label,
        period=period_tuple,
        account=account or None,
    )
    snap = svc.last_snapshot()
    return request.app.state.templates.TemplateResponse(
        request,
        "_portfolio_kpis.html",
        {
            "kpis": kpis,
            "snapshot": snap,
            "wash_impact_total": wi.disallowed_total,
            "wash_violations": wi.violation_count,
        },
    )


PAGE_SIZE = 25


PAGE_SIZE_OPTIONS = (10, 25, 50, 100)


@router.get("/portfolio/positions", response_class=HTMLResponse)
def portfolio_positions(
    request: Request,
    period: str | None = None,
    account: str | None = None,
    group_options: str = "merge",
    show: str = "open",  # "open" | "all"
    page: int = 1,
    page_size: int = PAGE_SIZE,
    symbols: str | None = None,
    repo: Repository = Depends(get_repository),
    svc: PricingService = Depends(get_pricing_service),
) -> HTMLResponse:
    today = date.today()
    period_tuple, period_label = _parse_period(period, today.year)
    trades = repo.all_trades()
    lots = repo.all_lots()
    gl_closures = repo.get_equity_gl_closures()
    all_lot_tickers = sorted({lot.ticker for lot in lots if lot.option_details is None})
    prices = svc.get_prices(all_lot_tickers)
    include_closed = show == "all"
    rows = compute_open_positions(
        trades=trades,
        lots=lots,
        prices=prices,
        period=period_tuple,
        account=account or None,
        include_closed=include_closed,
        gl_closures=gl_closures,
    )
    selected_symbols: set[str] = set()
    if symbols:
        selected_symbols = {s.strip().upper() for s in symbols.split(",") if s.strip()}
    if selected_symbols:
        rows = [r for r in rows if r.symbol.upper() in selected_symbols]
    if page_size not in PAGE_SIZE_OPTIONS:
        page_size = PAGE_SIZE
    total_rows = len(rows)
    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    page_rows = rows[start : start + page_size]
    symbol_filter_config = {
        "selected": sorted(selected_symbols),
        "all": sorted({r.symbol for r in rows} | selected_symbols),
        "qsTemplate": (
            f"period={period or 'ytd'}&account={account or ''}"
            f"&group_options={group_options}"
            f"&symbols={'%2C'.join(sorted(selected_symbols))}"
        ),
        "show": show,
        "pageSize": page_size,
    }
    return request.app.state.templates.TemplateResponse(
        request,
        "_portfolio_table.html",
        {
            "rows": page_rows,
            "period_label": period_label,
            "show": show,
            "page": page,
            "total_pages": total_pages,
            "total_rows": total_rows,
            "page_size": page_size,
            "page_size_options": PAGE_SIZE_OPTIONS,
            "selected_symbols": sorted(selected_symbols),
            "symbol_filter_config": symbol_filter_config,
            "selected_period": period or "ytd",
            "selected_account": account or "",
            "group_options": group_options,
        },
    )


@router.get("/portfolio/allocation", response_class=HTMLResponse)
def portfolio_allocation_fragment(
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
    positions = compute_open_positions(
        trades=trades,
        lots=lots,
        prices=prices,
        period=(today.year, today.year + 1),
        account=account or None,
    )
    allocation = build_allocation(positions=positions, top_n=10)
    return request.app.state.templates.TemplateResponse(
        request,
        "_portfolio_allocation.html",
        {"allocation": allocation},
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


@router.get("/portfolio/wash-watch", response_class=HTMLResponse)
def portfolio_wash_watch_fragment(
    request: Request,
    account: str | None = None,
    window_days: int = 30,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    rows = recent_loss_closes(
        repo=repo,
        today=date.today(),
        window_days=window_days,
        account=account or None,
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "_portfolio_wash_watch.html",
        {"rows": rows, "window_days": window_days},
    )


@router.get("/portfolio/body", response_class=HTMLResponse)
def portfolio_body(
    request: Request,
    period: str | None = None,
    account: str | None = None,
    repo: Repository = Depends(get_repository),
    svc: PricingService = Depends(get_pricing_service),
) -> HTMLResponse:
    """Bundled fragment: KPIs + equity-curve + allocation + wash-watch.

    Loads trades/lots/prices ONCE and feeds the existing pure compute
    functions, replacing the 5-way page-load fan-out on /portfolio.
    """
    today = date.today()
    period_tuple, period_label = _parse_period(period, today.year)
    year = period_tuple[0] if period_tuple else today.year

    all_trades = repo.all_trades()
    all_lots = repo.all_lots()
    if account:
        scoped_trades = [t for t in all_trades if t.account == account]
        scoped_lots = [lot for lot in all_lots if lot.account == account]
    else:
        scoped_trades = all_trades
        scoped_lots = all_lots
    symbols = sorted({lot.ticker for lot in scoped_lots if lot.option_details is None})
    prices = svc.get_prices(symbols)
    snap = svc.last_snapshot()

    kpis = compute_kpis(
        trades=scoped_trades,
        lots=scoped_lots,
        prices=prices,
        period_label=period_label,
        period=period_tuple,
        account=None,  # already filtered above
    )
    wi = compute_wash_impact(
        violations=repo.all_violations(),
        period_label=period_label,
        period=period_tuple,
        account=account or None,
    )
    points = build_equity_curve(trades=scoped_trades, year=year, present_unrealized=kpis.period_unrealized)
    positions_for_alloc = compute_open_positions(
        trades=scoped_trades,
        lots=scoped_lots,
        prices=prices,
        period=(today.year, today.year + 1),
        account=None,
    )
    allocation = build_allocation(positions=positions_for_alloc, top_n=10)
    wash_rows = recent_loss_closes(
        repo=repo,
        today=today,
        window_days=30,
        account=account or None,
    )

    return request.app.state.templates.TemplateResponse(
        request,
        "_portfolio_body.html",
        {
            "kpis": kpis,
            "snapshot": snap,
            "wash_impact_total": wi.disallowed_total,
            "wash_violations": wi.violation_count,
            "points": points,
            "year": year,
            "allocation": allocation,
            "rows": wash_rows,
            "window_days": 30,
        },
    )
