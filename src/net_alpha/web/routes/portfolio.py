from __future__ import annotations

from datetime import date, timedelta
from datetime import date as _date
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from net_alpha.audit import (
    CashRef,
    NetContributedRef,
    Period,
    RealizedPLRef,
    UnrealizedPLRef,
    WashImpactRef,
)
from net_alpha.config import TaxConfig
from net_alpha.db.repository import Repository
from net_alpha.inbox.aggregator import gather_inbox
from net_alpha.inbox.config import load_inbox_config
from net_alpha.inbox.dismissals import toggle_dismissal
from net_alpha.portfolio.account_value import account_value_at, build_account_value_series, build_eval_dates
from net_alpha.portfolio.allocation import build_allocation
from net_alpha.portfolio.cash_flow import (
    build_cash_balance_series,
    cash_allocation_slice,
    compute_cash_kpis,
)
from net_alpha.portfolio.freshness import compute_price_freshness
from net_alpha.portfolio.pnl import compute_kpis, compute_wash_impact
from net_alpha.portfolio.positions import (
    compute_open_option_positions,
    compute_open_positions,
    compute_open_short_option_positions,
)
from net_alpha.portfolio.tax_planner import (
    MissingTaxConfig,
    TaxBrackets,
    compute_offset_budget,
    project_year_end_tax,
)
from net_alpha.portfolio.top_movers import build_top_movers
from net_alpha.portfolio.wash_watch import recent_loss_closes
from net_alpha.prefs.profile import resolve_effective_profile
from net_alpha.pricing.service import PricingService
from net_alpha.web.dependencies import get_pricing_service, get_repository

router = APIRouter()

# Forward-fill window mirrored from account_value._FORWARD_FILL_DAYS so the
# warm range covers the dates the per-(ticker,date) loop will actually probe.
_CURVE_WARM_PADDING_DAYS = 7


def _warm_historical_for_curve(
    *,
    svc: PricingService,
    eval_dates: list[date],
    equity_lots: list,
    benchmark_symbol: str | None,
) -> None:
    """Bulk-prefetch closes for every (equity ticker + benchmark, date) the
    curve builder will probe. Without this, Lifetime view fan-outs to ~12K
    sequential Yahoo calls and Yahoo rate-limits us into a hung request."""
    if not eval_dates:
        return
    equity_tickers = sorted({lot.ticker for lot in equity_lots if lot.option_details is None})
    # Skip when there's no portfolio history — the curve is trivially empty
    # and warming the benchmark alone produces no useful chart.
    if not equity_tickers:
        return
    tickers = list(equity_tickers)
    if benchmark_symbol:
        tickers.append(benchmark_symbol)
    warm_start = min(eval_dates) - timedelta(days=_CURVE_WARM_PADDING_DAYS)
    warm_end = max(eval_dates)
    svc.warm_historical_range(tickers, warm_start, warm_end)


def _resolve_profile(repo: Repository, account: str | None):
    prefs = repo.list_user_preferences()
    filter_id = _resolve_account_id(account, repo)
    return resolve_effective_profile(prefs=prefs, filter_account_id=filter_id)


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


def _resolve_account_id(account: str | None, repo: Repository) -> int | None:
    """Resolve an account display string (e.g. 'Schwab/Tax') to its DB id, or None for all."""
    if not account:
        return None
    for a in repo.list_accounts():
        if f"{a.broker}/{a.label}" == account:
            return a.id
    return None


def _build_metric_refs(
    period_tuple: tuple[int, int] | None,
    period_label: str,
    account_id: int | None,
) -> dict[str, object]:
    """Pre-compute one MetricRef per KPI cell on the Portfolio dashboard."""
    refs: dict[str, object] = {
        "lifetime_realized": RealizedPLRef(
            kind="realized_pl",
            period=Period(start=_date(1970, 1, 1), end=_date(2100, 1, 1), label="Lifetime"),
            account_id=account_id,
            symbol=None,
        ),
        "lifetime_unrealized": UnrealizedPLRef(
            kind="unrealized_pl",
            account_id=account_id,
            symbol=None,
        ),
        "period_unrealized": UnrealizedPLRef(
            kind="unrealized_pl",
            account_id=account_id,
            symbol=None,
        ),
        "cash": CashRef(kind="cash", account_id=account_id),
    }
    if period_tuple is not None:
        period = Period(
            start=_date(period_tuple[0], 1, 1),
            end=_date(period_tuple[1], 1, 1),
            label=period_label,
        )
        refs["realized_period"] = RealizedPLRef(
            kind="realized_pl",
            period=period,
            account_id=account_id,
            symbol=None,
        )
        refs["wash_impact_period"] = WashImpactRef(
            kind="wash_impact",
            period=period,
            account_id=account_id,
        )
        refs["net_contributed_period"] = NetContributedRef(
            kind="net_contributed",
            period=period,
            account_id=account_id,
        )
    return refs


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
    svc: PricingService = Depends(get_pricing_service),
) -> HTMLResponse:
    imports = repo.list_imports()
    accounts = sorted({imp.account_display for imp in imports})

    today = date.today()
    current_year = today.year
    import_years = {imp.imported_at.year for imp in imports}
    available_years = sorted(import_years | {current_year}, reverse=True)

    selected_period = period or "ytd"
    snap = svc.last_snapshot()
    price_freshness, price_freshness_label = compute_price_freshness(snap)
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
            "price_freshness": price_freshness,
            "price_freshness_label": price_freshness_label,
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
        gl_lots=repo.list_all_gl_lots(),
    )
    wi = compute_wash_impact(
        violations=repo.all_violations(),
        period_label=period_label,
        period=period_tuple,
        account=account or None,
    )
    snap = svc.last_snapshot()
    account_id = _resolve_account_id(account, repo)
    # Open shorts (CSPs) — used for cash-secured / pledged-cash badges in the
    # Cash KPI tile so the user can see how much of their cash is collateral.
    scoped_trades_for_shorts = [t for t in trades if t.account == account] if account else trades
    open_shorts = compute_open_short_option_positions(
        scoped_trades_for_shorts,
        gl_option_closures=repo.get_option_gl_closures(),
    )
    cash_secured_total = sum((s.cash_secured for s in open_shorts), start=Decimal("0"))
    csp_count = sum(1 for s in open_shorts if s.call_put == "P")
    offset_budget = compute_offset_budget(repo=repo, year=today.year)
    cfg = request.app.state.tax_brackets_cfg
    projection = None
    has_tax_config = cfg is not None
    if cfg is not None:
        brackets = TaxBrackets(
            filing_status=cfg.filing_status,
            state=cfg.state,
            federal_marginal_rate=cfg.federal_marginal_rate,
            state_marginal_rate=cfg.state_marginal_rate,
            ltcg_rate=cfg.ltcg_rate,
            qualified_div_rate=cfg.qualified_div_rate,
        )
        try:
            projection = project_year_end_tax(repo=repo, year=today.year, brackets=brackets)
        except MissingTaxConfig:
            projection = None
            has_tax_config = False
    profile = _resolve_profile(repo, account)

    # Cash KPIs — needed for the Cash tile and for total_account_value.
    cash_events = repo.list_cash_events(account_id=None)
    if account:
        cash_events = [e for e in cash_events if e.account == account]
        scoped_trades_for_cash = [t for t in trades if t.account == account]
    else:
        scoped_trades_for_cash = trades
    holdings_value = kpis.open_position_value or Decimal("0")
    # Period start anchor for Total Return — account value at the close of the day
    # before the period began. Lifetime → 0; YTD/year → value on Dec 31 prior.
    if period_tuple is None:
        period_starting_value = Decimal("0")
    else:
        boundary = date(period_tuple[0], 1, 1) - timedelta(days=1)
        cash_points_for_anchor = build_cash_balance_series(
            events=cash_events,
            trades=scoped_trades_for_cash,
            account=None,
            period=None,  # need full history through the boundary
        )
        scoped_lots_for_anchor = [lt for lt in lots if lt.account == account] if account else lots
        period_starting_value = account_value_at(
            on=boundary,
            trades=scoped_trades_for_cash,
            lots=scoped_lots_for_anchor,
            cash_points=cash_points_for_anchor,
            get_close=svc.get_historical_close,
        )
    cash_kpis = compute_cash_kpis(
        events=cash_events,
        trades=scoped_trades_for_cash,
        holdings_value=holdings_value,
        account=None,  # events + trades are pre-scoped above
        period=period_tuple,
        period_starting_value=period_starting_value,
    )

    # Hero / Today tile context.
    total_account_value: Decimal | None = (
        (kpis.open_position_value + cash_kpis.cash_balance) if kpis.open_position_value is not None else None
    )
    vs_contributed_delta: Decimal | None = (
        (total_account_value - cash_kpis.net_contributions) if total_account_value is not None else None
    )

    return request.app.state.templates.TemplateResponse(
        request,
        "_portfolio_kpis.html",
        {
            "kpis": kpis,
            "snapshot": snap,
            "wash_impact_total": wi.disallowed_total,
            "wash_violations": wi.violation_count,
            "metric_refs": _build_metric_refs(period_tuple, period_label, account_id),
            "offset_budget": offset_budget,
            "projection": projection,
            "has_tax_config": has_tax_config,
            "profile": profile,
            "cash_secured_total": cash_secured_total,
            "csp_count": csp_count,
            "cash_kpis": cash_kpis,
            "total_account_value": total_account_value,
            "vs_contributed_delta": vs_contributed_delta,
            "selected_period": period or "ytd",
            "selected_account": account or "",
        },
    )


PAGE_SIZE = 25


PAGE_SIZE_OPTIONS = (10, 25, 50, 100)


_SORT_KEYS: dict[str, callable] = {
    "symbol": lambda r: r.symbol.upper(),
    "qty": lambda r: r.qty,
    "market_value": lambda r: r.market_value,
    "open_cost": lambda r: r.open_cost,
    "avg_basis": lambda r: r.avg_basis,
    "cash_sunk": lambda r: r.cash_sunk_per_share,
    "unrealized": lambda r: r.unrealized_pl,
}


def _sort_rows(rows: list, sort: str | None, direction: str | None) -> list:
    """Sort holdings rows by a stable key. None values are pushed to the end
    regardless of direction so the user always sees priced rows first."""
    key_fn = _SORT_KEYS.get(sort or "")
    if key_fn is None:
        # Default: market_value desc with None last (the historical behavior).
        priced = [r for r in rows if r.market_value is not None]
        unpriced = [r for r in rows if r.market_value is None]
        priced.sort(key=lambda r: r.market_value, reverse=True)
        return priced + unpriced
    desc = (direction or "desc").lower() == "desc"
    has = [r for r in rows if key_fn(r) is not None]
    none_rows = [r for r in rows if key_fn(r) is None]
    has.sort(key=key_fn, reverse=desc)
    return has + none_rows


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
    q: str | None = None,
    sort: str | None = None,
    dir: str | None = None,
    repo: Repository = Depends(get_repository),
    svc: PricingService = Depends(get_pricing_service),
) -> HTMLResponse:
    today = date.today()
    period_tuple, period_label = _parse_period(period, today.year)
    trades = repo.all_trades()
    lots = repo.all_lots()
    gl_closures = repo.get_equity_gl_closures()
    gl_option_closures = repo.get_option_gl_closures()
    all_lot_tickers = sorted({lot.ticker for lot in lots if lot.option_details is None})
    prices = svc.get_prices(all_lot_tickers)
    include_closed = show == "all"
    all_rows = compute_open_positions(
        trades=trades,
        lots=lots,
        prices=prices,
        period=period_tuple,
        account=account or None,
        include_closed=include_closed,
        gl_closures=gl_closures,
        gl_option_closures=gl_option_closures,
        gl_lots=repo.list_all_gl_lots(),
    )
    selected_symbols: set[str] = set()
    if symbols:
        selected_symbols = {s.strip().upper() for s in symbols.split(",") if s.strip()}
    # Universe for the symbol-picker reflects the current Show mode (Open vs All)
    # — independent of any active selection, so the user can pick a different
    # symbol after applying a filter. Selected symbols outside that universe are
    # not surfaced (e.g. you selected "GPRO" while in Show=All, then switched to
    # Show=Open — GPRO is closed and shouldn't reappear in the picker).
    universe = {r.symbol for r in all_rows}
    if selected_symbols:
        rows = [r for r in all_rows if r.symbol.upper() in selected_symbols]
    else:
        rows = list(all_rows)
    # Free-form substring filter on the underlying symbol — driven by the
    # page-level search input on /positions. Lets matches on later pages
    # surface (the client-side DOM filter only sees the current page).
    q_clean = (q or "").strip().upper()
    if q_clean:
        rows = [r for r in rows if q_clean in r.symbol.upper()]
    rows = _sort_rows(rows, sort, dir)
    if page_size not in PAGE_SIZE_OPTIONS:
        page_size = PAGE_SIZE
    total_rows = len(rows)
    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    page_rows = rows[start : start + page_size]
    symbol_filter_config = {
        "selected": sorted(selected_symbols),
        "all": sorted(universe),
        "qsTemplate": (
            f"period={period or 'ytd'}&account={account or ''}"
            f"&group_options={group_options}"
            f"&symbols={'%2C'.join(sorted(selected_symbols))}"
        ),
        "show": show,
        "pageSize": page_size,
    }
    profile = _resolve_profile(repo, account)
    extra_columns = profile.default_columns("holdings")
    # Inject targets-by-symbol + 'target' column when any targets exist.
    targets = repo.list_targets()
    targets_by_symbol = {t.symbol: t for t in targets}
    if targets and "target" not in extra_columns:
        extra_columns = list(extra_columns) + ["target"]
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
            "profile": profile,
            "extra_columns": extra_columns,
            "targets_by_symbol": targets_by_symbol,
            "sort": sort or "market_value",
            "dir": (dir or "desc").lower(),
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
        gl_closures=repo.get_equity_gl_closures(),
        gl_option_closures=repo.get_option_gl_closures(),
        gl_lots=repo.list_all_gl_lots(),
    )
    allocation = build_allocation(positions=positions, top_n=10)
    return request.app.state.templates.TemplateResponse(
        request,
        "_portfolio_allocation.html",
        {"allocation": allocation},
    )


@router.get("/holdings/options", response_class=HTMLResponse)
def holdings_options(
    request: Request,
    account: str | None = None,
    page: int = 1,
    page_size: int = 25,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    """All open option positions (long + short) panel — rendered on /holdings.

    Pure read of trades + lots + GL closures, scoped by account. Sorted by
    expiry so the next contract to roll/manage is always at the top.
    """
    today = date.today()
    trades = repo.all_trades()
    lots = repo.all_lots()
    open_options = compute_open_option_positions(
        trades,
        lots,
        account=account or None,
        gl_closures=repo.get_equity_gl_closures(),
        gl_option_closures=repo.get_option_gl_closures(),
    )
    cash_secured_total = sum((o.cash_secured for o in open_options), start=Decimal("0"))
    premium_received_total = sum((o.cash_basis for o in open_options if o.side == "short"), start=Decimal("0"))
    long_cost_total = sum((o.cash_basis for o in open_options if o.side == "long"), start=Decimal("0"))
    # 3-card mini-summary for the panel header (H7). Net premium signs short
    # premium received as a credit and long cost paid as a debit. Avg DTE is
    # qty-weighted across all open contracts (clamped to 0 when nothing open).
    total_qty = sum((o.qty for o in open_options), start=Decimal("0"))
    if total_qty > 0:
        avg_dte = sum(((o.expiry - today).days * o.qty for o in open_options), start=Decimal("0")) / total_qty
    else:
        avg_dte = Decimal("0")
    options_summary = {
        "open_contracts": total_qty,
        "net_premium": premium_received_total - long_cost_total,
        "avg_dte": avg_dte,
    }
    # Compute per-side/per-type counts from the full (pre-slice) list so the
    # summary header reflects totals even when pagination is active.
    long_count = sum(1 for o in open_options if o.side == "long")
    short_count = sum(1 for o in open_options if o.side == "short")
    put_count = sum(1 for o in open_options if o.call_put == "P")
    call_count = sum(1 for o in open_options if o.call_put == "C")
    option_counts = {
        "long": long_count,
        "short": short_count,
        "puts": put_count,
        "calls": call_count,
    }

    page_size_norm = page_size if page_size in (10, 25, 50, 100) else 25
    page_norm = max(1, page)
    total_rows = len(open_options)
    total_pages = max(1, (total_rows + page_size_norm - 1) // page_size_norm)
    page_norm = min(page_norm, total_pages)
    start_idx = (page_norm - 1) * page_size_norm
    end_idx = start_idx + page_size_norm
    open_options_page = open_options[start_idx:end_idx]
    pagination = {
        "page": page_norm,
        "page_size": page_size_norm,
        "total_pages": total_pages,
        "total_rows": total_rows,
        "page_size_options": (10, 25, 50, 100),
    }

    return request.app.state.templates.TemplateResponse(
        request,
        "_portfolio_open_options.html",
        {
            "open_options": open_options_page,
            "cash_secured_total": cash_secured_total,
            "premium_received_total": premium_received_total,
            "long_cost_total": long_cost_total,
            "options_summary": options_summary,
            "option_counts": option_counts,
            "today": today,
            "selected_account": account or "",
            "pagination": pagination,
        },
    )


@router.get("/holdings/short-options", response_class=HTMLResponse)
def holdings_short_options_legacy(
    request: Request,
    account: str | None = None,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    """Backwards-compat alias — renders the unified options panel."""
    return holdings_options(request, account=account, repo=repo)


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

    trades = repo.all_trades()
    lots = repo.all_lots()
    if account:
        trades = [t for t in trades if t.account == account]
        lots = [lot for lot in lots if lot.account == account]

    cash_events = repo.list_cash_events(account_id=None)
    if account:
        cash_events = [e for e in cash_events if e.account == account]

    cash_points = build_cash_balance_series(
        events=cash_events,
        trades=trades,
        account=None,
        period=period_tuple,
    )

    event_dates = sorted({t.date for t in trades} | {e.event_date for e in cash_events})
    eval_dates = build_eval_dates(period=period_tuple, today=today, event_dates=event_dates)

    benchmark_symbol = request.app.state.pricing_config.benchmark_symbol
    _warm_historical_for_curve(
        svc=svc,
        eval_dates=eval_dates,
        equity_lots=lots,
        benchmark_symbol=benchmark_symbol,
    )

    account_points = build_account_value_series(
        trades=trades,
        lots=lots,
        cash_points=cash_points,
        eval_dates=eval_dates,
        get_close=svc.get_historical_close,
    )

    benchmark_points: list = []

    return request.app.state.templates.TemplateResponse(
        request,
        "_portfolio_equity_curve.html",
        {
            "account_points": account_points,
            "benchmark_points": benchmark_points,
            "benchmark_symbol": benchmark_symbol,
            "period_label": period_label,
        },
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

    gl_lots_all = repo.list_all_gl_lots()
    gl_lots_scoped = [g for g in gl_lots_all if g.account_display == account] if account else gl_lots_all
    kpis = compute_kpis(
        trades=scoped_trades,
        lots=scoped_lots,
        prices=prices,
        period_label=period_label,
        period=period_tuple,
        account=None,  # already filtered above
        gl_lots=gl_lots_scoped,
    )
    # Hoist gl_option_closures so we don't re-scan the table for both
    # compute_open_positions and compute_open_short_option_positions.
    gl_option_closures = repo.get_option_gl_closures()
    positions_for_alloc = compute_open_positions(
        trades=scoped_trades,
        lots=scoped_lots,
        prices=prices,
        period=(today.year, today.year + 1),
        account=None,
        gl_closures=repo.get_equity_gl_closures(),
        gl_option_closures=gl_option_closures,
        gl_lots=gl_lots_scoped,
    )

    top_movers = build_top_movers(positions_for_alloc)

    # --- Cash flow ---
    cash_events = repo.list_cash_events(account_id=None)
    if account:
        cash_events = [e for e in cash_events if e.account == account]
    # Use the same total `compute_kpis` already produced for the Hero tile and
    # `account_value_at` (period-start anchor) — both include open long-option
    # lots carried at basis. Summing `compute_open_positions` market values
    # alone skips those lots (it only iterates equity), which made the Total
    # Return tile read low by the long-option-basis amount and disagree with
    # the Hero tile and the explain panel on the same page.
    holdings_value_total = kpis.open_position_value or Decimal("0")
    # Period start anchor for Total Return — account value at the close of the day
    # before the period began. Lifetime → 0; YTD/year → value on Dec 31 prior.
    if period_tuple is None:
        period_starting_value = Decimal("0")
    else:
        boundary = date(period_tuple[0], 1, 1) - timedelta(days=1)
        cash_points_for_anchor = build_cash_balance_series(
            events=cash_events,
            trades=scoped_trades,
            account=None,
            period=None,  # need full history through the boundary
        )
        period_starting_value = account_value_at(
            on=boundary,
            trades=scoped_trades,
            lots=scoped_lots,
            cash_points=cash_points_for_anchor,
            get_close=svc.get_historical_close,
        )
    cash_kpis = compute_cash_kpis(
        events=cash_events,
        trades=scoped_trades,
        holdings_value=holdings_value_total,
        account=None,  # already filtered above
        period=period_tuple,
        period_starting_value=period_starting_value,
    )
    cash_points = build_cash_balance_series(
        events=cash_events,
        trades=scoped_trades,
        account=None,
        period=period_tuple,
    )
    cash_slice = cash_allocation_slice(
        events=cash_events,
        trades=scoped_trades,
        account=None,
    )

    # Account-value series (the redesigned equity curve). Built off the same
    # cash_points + an event-anchored eval-date axis. See
    # docs/superpowers/specs/2026-05-02-equity-curve-redesign-design.md.
    account_event_dates = sorted({t.date for t in scoped_trades} | {e.event_date for e in cash_events})
    account_eval_dates = build_eval_dates(
        period=period_tuple,
        today=today,
        event_dates=account_event_dates,
    )
    benchmark_symbol = request.app.state.pricing_config.benchmark_symbol
    _warm_historical_for_curve(
        svc=svc,
        eval_dates=account_eval_dates,
        equity_lots=scoped_lots,
        benchmark_symbol=benchmark_symbol,
    )
    account_points = build_account_value_series(
        trades=scoped_trades,
        lots=scoped_lots,
        cash_points=cash_points,
        eval_dates=account_eval_dates,
        get_close=svc.get_historical_close,
    )

    benchmark_points: list = []

    open_shorts = compute_open_short_option_positions(
        scoped_trades,
        gl_option_closures=gl_option_closures,
    )
    cash_secured_total = sum(
        (s.cash_secured for s in open_shorts),
        start=Decimal("0"),
    )
    allocation = build_allocation(
        positions=positions_for_alloc,
        top_n=10,
        cash=cash_slice,
        cash_pledged=cash_secured_total,
    )
    premium_received_total = sum(
        (s.premium_received for s in open_shorts),
        start=Decimal("0"),
    )
    csp_count = sum(1 for s in open_shorts if s.call_put == "P")

    account_id = _resolve_account_id(account, repo)
    offset_budget = compute_offset_budget(repo=repo, year=today.year)
    cfg = request.app.state.tax_brackets_cfg
    projection = None
    has_tax_config = cfg is not None
    if cfg is not None:
        brackets = TaxBrackets(
            filing_status=cfg.filing_status,
            state=cfg.state,
            federal_marginal_rate=cfg.federal_marginal_rate,
            state_marginal_rate=cfg.state_marginal_rate,
            ltcg_rate=cfg.ltcg_rate,
            qualified_div_rate=cfg.qualified_div_rate,
        )
        try:
            projection = project_year_end_tax(repo=repo, year=today.year, brackets=brackets)
        except MissingTaxConfig:
            projection = None
            has_tax_config = False
    profile = _resolve_profile(repo, account)

    # Hero / Today tile context (same as portfolio_kpis handler).
    body_total_account_value: Decimal | None = (
        (kpis.open_position_value + cash_kpis.cash_balance) if kpis.open_position_value is not None else None
    )
    body_vs_contributed_delta: Decimal | None = (
        (body_total_account_value - cash_kpis.net_contributions) if body_total_account_value is not None else None
    )

    return request.app.state.templates.TemplateResponse(
        request,
        "_portfolio_body.html",
        {
            "kpis": kpis,
            "snapshot": snap,
            "allocation": allocation,
            "open_shorts": open_shorts,
            "cash_secured_total": cash_secured_total,
            "premium_received_total": premium_received_total,
            "csp_count": csp_count,
            "today": today,
            "cash_kpis": cash_kpis,
            "cash_points": cash_points,
            "cash_slice": cash_slice,
            "metric_refs": _build_metric_refs(period_tuple, period_label, account_id),
            "offset_budget": offset_budget,
            "projection": projection,
            "has_tax_config": has_tax_config,
            "profile": profile,
            "total_account_value": body_total_account_value,
            "vs_contributed_delta": body_vs_contributed_delta,
            "top_movers": top_movers,
            "benchmark_points": benchmark_points,
            "benchmark_symbol": benchmark_symbol,
            "account_points": account_points,
            "period_label": period_label,
            "account": account,  # used by the inbox lazy-load wrapper
            "selected_period": period or "ytd",
            "selected_account": account or "",
        },
    )


def _resolve_inbox_rates(tax: TaxConfig | None) -> tuple[Decimal, Decimal]:
    """Pull (short-term, long-term) effective rates from the cached tax config.

    ST = federal_marginal_rate + state_marginal_rate (ordinary income on ST gains)
    LT = ltcg_rate + state_marginal_rate (LTCG federal + state)

    Falls back to (0, 0) when no tax config is set — the LT-eligibility signal
    still emits items, but with dollar_impact = None, which the template
    renders without the +$X clause.

    Reads from app.state.tax_brackets_cfg (loaded once at startup, refreshed
    by the /settings POST) rather than re-reading config.yaml per request, so
    the inbox stays in sync with the rest of the dashboard's tax projections.
    """
    if tax is None:
        return Decimal("0"), Decimal("0")
    st = Decimal(str(tax.federal_marginal_rate)) + Decimal(str(tax.state_marginal_rate))
    lt = Decimal(str(tax.ltcg_rate)) + Decimal(str(tax.state_marginal_rate))
    return st, lt


@router.get("/portfolio/inbox", response_class=HTMLResponse)
def portfolio_inbox(
    request: Request,
    account: str | None = Query(default=None),
    repo: Repository = Depends(get_repository),
    pricing: PricingService = Depends(get_pricing_service),
):
    cfg = load_inbox_config(Path.home() / ".net_alpha" / "config.yaml")
    st_rate, lt_rate = _resolve_inbox_rates(request.app.state.tax_brackets_cfg)
    today = _date.today()
    with Session(repo.engine) as session:
        items = gather_inbox(
            repo=repo,
            prices=pricing,
            session=session,
            today=today,
            config=cfg,
            st_rate=st_rate,
            lt_rate=lt_rate,
            account=account,
        )
    return request.app.state.templates.TemplateResponse(
        request,
        "_portfolio_inbox.html",
        {"items": items, "account": account},
    )


@router.post("/portfolio/inbox/dismiss/{dismiss_key:path}", response_class=HTMLResponse)
def portfolio_inbox_dismiss(
    request: Request,
    dismiss_key: str,
    account: str | None = Query(default=None),
    repo: Repository = Depends(get_repository),
    pricing: PricingService = Depends(get_pricing_service),
):
    with Session(repo.engine) as session:
        toggle_dismissal(session, dismiss_key)
    return portfolio_inbox(request=request, account=account, repo=repo, pricing=pricing)


@router.get("/portfolio/explain/total-return", response_class=HTMLResponse)
def explain_total_return(
    request: Request,
    period: str | None = None,
    account: str | None = None,
    repo: Repository = Depends(get_repository),
    svc: PricingService = Depends(get_pricing_service),
) -> HTMLResponse:
    """Math explainer fragment for the Total Return KPI tile."""
    from net_alpha.portfolio.explain import build_total_return_breakdown

    today = date.today()
    period_tuple, period_label = _parse_period(period, today.year)

    trades = repo.all_trades()
    lots = repo.all_lots()
    if account:
        trades = [t for t in trades if t.account == account]
        lots = [lt for lt in lots if lt.account == account]
    cash_events = repo.list_cash_events(account_id=None)
    if account:
        cash_events = [e for e in cash_events if e.account == account]

    cash_points_full = build_cash_balance_series(
        events=cash_events,
        trades=trades,
        account=None,
        period=None,
    )

    if period_tuple is None:
        starting_value = Decimal("0")
        is_lifetime = True
    else:
        boundary = date(period_tuple[0], 1, 1) - timedelta(days=1)
        starting_value = account_value_at(
            on=boundary,
            trades=trades,
            lots=lots,
            cash_points=cash_points_full,
            get_close=svc.get_historical_close,
        )
        is_lifetime = False

    symbols = sorted({lot.ticker for lot in lots if lot.option_details is None})
    prices = svc.get_prices(symbols) if symbols else {}
    kpis_now = compute_kpis(
        trades=trades,
        lots=lots,
        prices=prices,
        period_label=period_label,
        period=period_tuple,
        account=None,
        gl_lots=repo.list_all_gl_lots(),
    )
    holdings_value = kpis_now.open_position_value or Decimal("0")
    cash_kpis = compute_cash_kpis(
        events=cash_events,
        trades=trades,
        holdings_value=holdings_value,
        account=None,
        period=period_tuple,
        period_starting_value=starting_value,
    )

    breakdown = build_total_return_breakdown(
        period_label=period_label,
        ending_value=cash_kpis.account_value,
        starting_value=starting_value,
        contributions=cash_kpis.period_net_contributions,
        realized_in_period=kpis_now.period_realized,
        is_lifetime=is_lifetime,
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "_explain_total_return.html",
        {"b": breakdown},
    )


@router.get("/portfolio/explain/unrealized", response_class=HTMLResponse)
def explain_unrealized(
    request: Request,
    account: str | None = None,
    repo: Repository = Depends(get_repository),
    svc: PricingService = Depends(get_pricing_service),
) -> HTMLResponse:
    """Math explainer fragment for the Unrealized P/L KPI tile.

    Period-agnostic — Unrealized always shows current open positions.
    """
    from net_alpha.portfolio.explain import build_unrealized_breakdown
    from net_alpha.portfolio.positions import consume_lots_fifo

    today = date.today()
    trades = repo.all_trades()
    lots = repo.all_lots()
    if account:
        trades = [t for t in trades if t.account == account]
        lots = [lt for lt in lots if lt.account == account]

    gl_closures = repo.get_equity_gl_closures()
    gl_option_closures = repo.get_option_gl_closures()
    if account:
        gl_closures = {k: v for k, v in gl_closures.items() if k[0] == account}
        gl_option_closures = {k: v for k, v in gl_option_closures.items() if k[0] == account}

    consumed = consume_lots_fifo(
        lots=lots,
        trades=trades,
        gl_closures=gl_closures,
        gl_option_closures=gl_option_closures,
    )
    short_rows = compute_open_short_option_positions(
        trades,
        gl_option_closures=gl_option_closures,
    )
    symbols = sorted({lot.ticker for lot in lots} | {row.ticker for row in short_rows})
    prices = svc.get_prices(symbols) if symbols else {}

    breakdown = build_unrealized_breakdown(
        consumed=consumed,
        short_option_rows=short_rows,
        prices=prices,
        as_of=today,
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "_explain_unrealized.html",
        {"b": breakdown},
    )


@router.get("/portfolio/explain/dismiss", response_class=HTMLResponse)
def explain_dismiss() -> HTMLResponse:
    """Empty fragment used by the explainer panels' close button."""
    return HTMLResponse("")
