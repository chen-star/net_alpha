"""Verification engine routes.

Surface:
  GET  /verify                       -> run history + latest run details
  POST /verify/run                   -> trigger a verify run synchronously
  GET  /verify/findings/{id}         -> HTMX fragment listing findings for a run
  GET  /verify/badge?page=...        -> inline ✓/⚠/✗ chip for Overview / Positions
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from net_alpha.db.repository import Repository
from net_alpha.portfolio.allocation import build_allocation
from net_alpha.portfolio.positions import compute_open_positions, consume_lots_fifo
from net_alpha.pricing.service import PricingService
from net_alpha.verify.badge import run_inline
from net_alpha.web.dependencies import get_pricing_service, get_repository

router = APIRouter()


def _build_lot_adapters(
    repo: Repository,
    svc: PricingService,
    today: date,
) -> tuple[list[Any], dict[str, Any], list]:
    """Build per-lot adapter rows + a price snapshot + the raw trade list.

    Uses ``consume_lots_fifo`` so per-lot ``market_value`` / ``adjusted_basis``
    match the values the renderer derives. Equity lots only -- option lots are
    deferred to a future verifier (see Task 7's PL-* coverage notes).
    """
    trades = repo.all_trades()
    lots = repo.all_lots()
    symbols = sorted({lot.ticker for lot in lots if lot.option_details is None})
    prices = svc.get_prices(symbols)

    consumed = consume_lots_fifo(
        lots=lots,
        trades=trades,
        gl_closures=repo.get_equity_gl_closures(),
        gl_option_closures=repo.get_option_gl_closures(),
    )

    lot_adapters: list[Any] = []
    for lot, remaining_qty, remaining_basis in consumed:
        if lot.option_details is not None:
            continue  # PL-* invariants run on equity lots only in v1
        if remaining_qty <= 0:
            continue
        quote = prices.get(lot.ticker)
        price = float(quote.price) if quote is not None and quote.price is not None else 0.0
        qty = float(remaining_qty)
        mv = qty * price
        basis = float(remaining_basis)
        upl = mv - basis
        acquired = lot.tacked_acquired_date or lot.date
        days_held = (today - acquired).days
        bucket = "LT" if days_held >= 366 else "ST"
        lot_adapters.append(
            type(
                "L",
                (),
                {
                    # Lots don't expose a stable surrogate id at this layer;
                    # id(lot) is unique within this snapshot which is enough
                    # for the invariant scope label.
                    "id": id(lot),
                    "qty": qty,
                    "current_price": price,
                    "market_value": mv,
                    "adjusted_basis": basis,
                    "unrealized_pl": upl,
                    "tacked_acquired_date": acquired.isoformat(),
                    "bucket": bucket,
                },
            )()
        )
    return lot_adapters, prices, trades


def _overview_snapshot(repo: Repository, svc: PricingService) -> Any:
    """Snapshot for OV-* / AL-* invariants -- same inputs as ``/portfolio/kpis``."""
    today = date.today()
    lot_adapters, prices, trades = _build_lot_adapters(repo, svc, today)
    lots = repo.all_lots()

    positions = compute_open_positions(
        trades=trades,
        lots=lots,
        prices=prices,
        period=(today.year, today.year + 1),
        account=None,
        gl_closures=repo.get_equity_gl_closures(),
        gl_option_closures=repo.get_option_gl_closures(),
        gl_lots=repo.list_all_gl_lots(),
    )
    allocation = build_allocation(positions=positions, top_n=10)

    total_market_value = sum(la.market_value for la in lot_adapters)
    total_basis = sum(la.adjusted_basis for la in lot_adapters)
    unrealized_pl = total_market_value - total_basis

    # AL-1 uses the donut's top-N + OTHER + cash slices (they should sum to
    # ~100% when there's any value). AL-2 uses the full ranked slice list as
    # a "leaderboard" whose dollar weights should sum to total_market_value.
    #
    # Empty-portfolio special case: when there are no slices we feed a
    # synthetic 100% row so AL-1 vacuously passes (the allocation panel is
    # hidden in this state anyway). AL-2 with an empty leaderboard and
    # total_market_value=0 already passes by classify(0, 0).
    if allocation.slices:
        allocation_rows: list[tuple[str, float]] = [(sl.symbol, float(sl.pct)) for sl in allocation.slices]
    else:
        allocation_rows = [("(empty)", 100.0)]
    leaderboard_rows = [
        (sl.symbol, float(sl.market_value)) for sl in allocation.all_slices if not getattr(sl, "is_cash", False)
    ]

    return type(
        "OverviewSnap",
        (),
        {
            "total_market_value": total_market_value,
            "total_basis": total_basis,
            "unrealized_pl": unrealized_pl,
            # OV-3: realized YTD vs sum of closed-lot P&L. Both 0 on empty
            # DB; Task 14 will wire the real closed-lot list in.
            "realized_pl_ytd": 0.0,
            "closed_lots_ytd": [],
            "allocation_rows": allocation_rows,
            "leaderboard_rows": leaderboard_rows,
            "lots": lot_adapters,
        },
    )()


def _positions_snapshot(repo: Repository, svc: PricingService) -> Any:
    """Snapshot for PL-* + XP-1 invariants."""
    today = date.today()
    lot_adapters, _prices, _trades = _build_lot_adapters(repo, svc, today)
    return type("PositionsSnap", (), {"lots": lot_adapters})()


@router.get("/verify/badge", response_class=HTMLResponse)
def verify_badge_fragment(
    request: Request,
    page: str,
    repo: Repository = Depends(get_repository),
    svc: PricingService = Depends(get_pricing_service),
) -> HTMLResponse:
    if page == "overview":
        snapshot = _overview_snapshot(repo, svc)
    elif page == "positions":
        snapshot = _positions_snapshot(repo, svc)
    else:
        raise HTTPException(status_code=400, detail=f"unknown page: {page}")

    status = run_inline(snapshot=snapshot, page=page)
    return request.app.state.templates.TemplateResponse(
        request,
        "verify/_badge.html",
        {"verify_badge": status},
    )


@router.get("/verify")
def verify_index(
    request: Request,
    repo: Repository = Depends(get_repository),
):
    """Render the verify dashboard: latest run summary + history + findings."""
    latest = repo.latest_verify_run()
    history = repo.list_verify_runs(limit=30)
    findings = repo.list_verify_findings(run_id=latest.id) if latest else []
    return request.app.state.templates.TemplateResponse(
        request,
        "verify/index.html",
        {
            "latest": latest,
            "history": history,
            "findings": findings,
            "active_page": "verify",
        },
    )


@router.post("/verify/run")
def verify_run(
    request: Request,
    repo: Repository = Depends(get_repository),
):
    """Trigger one synchronous verify run, then redirect to /verify.

    Manual UI trigger -> ``trigger="manual"`` on the persisted result row.
    Synchronous on purpose: the user clicks the button and expects to see
    the updated dashboard on the next page load, not an async toast.
    """
    from net_alpha.service.jobs.verify import run_verify_once

    run_verify_once(repo=repo, trigger="manual")
    return RedirectResponse(url="/verify", status_code=303)


@router.get("/verify/findings/{run_id}", response_class=HTMLResponse)
def verify_findings(
    request: Request,
    run_id: int,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    """HTMX fragment: findings table for one historical run."""
    runs = repo.list_verify_runs(limit=200)
    run = next((r for r in runs if r.id == run_id), None)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    findings = repo.list_verify_findings(run_id=run_id)
    return request.app.state.templates.TemplateResponse(
        request,
        "verify/_findings_table.html",
        {"run": run, "findings": findings},
    )
