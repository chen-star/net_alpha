from __future__ import annotations

from datetime import date as _date
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.engine.etf_pairs import load_etf_pairs
from net_alpha.engine.simulator import simulate_buy, simulate_sell
from net_alpha.portfolio.tax_planner import PlannedTrade, TaxBrackets, assess_trade
from net_alpha.pricing.service import PricingService
from net_alpha.web.dependencies import get_pricing_service, get_repository

router = APIRouter()


@router.get("/sim", response_class=HTMLResponse)
def sim_form(
    request: Request,
    repo: Repository = Depends(get_repository),
    pricing: PricingService = Depends(get_pricing_service),
    ticker: str | None = None,
    qty: str | None = None,
    harvest: str | None = None,
    account: str | None = None,
    action: str | None = None,
) -> HTMLResponse:
    """Render the trade-simulator form.

    Pre-fills ticker, quantity, account, action, and current-price hint
    when called from a contextual entry point (e.g. Positions row →
    ``?ticker=X&qty=N&account=Y&action=sell``).
    """
    sym = (ticker or "").upper().strip()
    qty_str = (qty or "").strip()
    account_pref = (account or "").strip()
    action_pref = (action or "").strip().lower()
    if action_pref not in ("buy", "sell"):
        action_pref = ""
    price_hint = ""
    if sym:
        quotes = pricing.get_prices([sym])
        q = quotes.get(sym)
        if q is not None and q.price is not None:
            price_hint = f"{float(q.price):.2f}"
    return request.app.state.templates.TemplateResponse(
        request,
        "sim.html",
        {
            "ticker": sym,
            "qty": qty_str,
            "account_pref": account_pref,
            "action_pref": action_pref,
            "price_hint": price_hint,
            "harvest_mode": bool(harvest),
            "tickers": repo.list_distinct_tickers(),
            "accounts": [a.display() for a in repo.list_accounts()],
            "today_iso": _date.today().isoformat(),
            "result": None,
        },
    )


@router.post("/sim", response_class=HTMLResponse)
def sim_run(
    request: Request,
    repo: Repository = Depends(get_repository),
    action: str = Form("sell"),
    ticker: str = Form(...),
    qty: float = Form(...),
    price: float = Form(...),
    account: str = Form(""),
    trade_date: str = Form(""),
) -> HTMLResponse:
    on_date = _date.fromisoformat(trade_date) if trade_date else _date.today()
    accounts = repo.list_accounts()
    accounts_filtered = [a for a in accounts if a.display() == account] if account else accounts

    # Build traffic-light signal for both buy and sell paths.
    account_id_for_signal = 0
    for a in accounts:
        if a.display() == (account or ""):
            account_id_for_signal = a.id or 0
            break

    planned = PlannedTrade(
        symbol=ticker.upper(),
        account_id=account_id_for_signal,
        action="Sell" if action.lower() == "sell" else "Buy",
        qty=Decimal(str(qty)),
        price=Decimal(str(price)),
        on=on_date,
    )
    cfg = request.app.state.tax_brackets_cfg
    brackets_for_signal: TaxBrackets | None = None
    if cfg is not None:
        brackets_for_signal = TaxBrackets(
            filing_status=cfg.filing_status,
            state=cfg.state,
            federal_marginal_rate=cfg.federal_marginal_rate,
            state_marginal_rate=cfg.state_marginal_rate,
            ltcg_rate=cfg.ltcg_rate,
            qualified_div_rate=cfg.qualified_div_rate,
        )
    signal = assess_trade(
        proposed=planned,
        repo=repo,
        brackets=brackets_for_signal,
        as_of=on_date,
        etf_pairs=request.app.state.etf_pairs,
    )

    if action.lower() == "buy":
        options = simulate_buy(
            ticker=ticker.upper(),
            qty=Decimal(str(qty)),
            price=Decimal(str(price)),
            account=account or None,
            on_date=on_date,
            accounts=accounts,
            recent_trades=repo.all_trades(),
            existing_violations=repo.all_violations(),
            etf_pairs=load_etf_pairs(),
        )
        return request.app.state.templates.TemplateResponse(
            request,
            "_sim_buy_result.html",
            {"options": options, "ticker": ticker.upper(), "signal": signal},
        )

    options = simulate_sell(
        ticker=ticker.upper(),
        qty=Decimal(str(qty)),
        price=Decimal(str(price)),
        accounts=accounts_filtered,
        existing_lots=repo.all_lots(),
        recent_trades=repo.all_trades(),
        today=on_date,
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "_sim_sell_result.html",
        {"options": options, "ticker": ticker.upper(), "signal": signal},
    )
