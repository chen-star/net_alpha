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


def _build_sim_positions(
    *,
    repo: Repository,
    pricing: PricingService,
) -> list:
    """Return Position objects for the sim suggestions, with FIFO-consumed
    quantities. Fully-closed positions are excluded; partially-closed
    positions reflect remaining quantity.

    Aggregation is per-symbol (not per (account, symbol)) — the chip's
    pre-fill account uses the alphabetically-first account when a symbol
    is held across multiple accounts. The user can change account on the
    sim form.
    """
    from net_alpha.portfolio.positions import compute_open_positions
    from net_alpha.portfolio.sim_suggestions import Position

    trades = repo.all_trades()
    lots = repo.all_lots()
    gl_closures = repo.get_equity_gl_closures()
    gl_option_closures = repo.get_option_gl_closures()
    gl_lots = repo.list_all_gl_lots()

    symbols = sorted({lot.ticker for lot in lots if lot.option_details is None})
    quotes = pricing.get_prices(symbols) if symbols else {}

    pos_rows = compute_open_positions(
        trades=trades,
        lots=lots,
        prices=quotes,
        period=None,
        account=None,
        include_closed=False,
        gl_closures=gl_closures,
        gl_option_closures=gl_option_closures,
        gl_lots=gl_lots,
    )

    positions: list = []
    for r in pos_rows:
        if r.qty is None or r.qty <= 0:
            continue
        if r.market_value is None:
            continue
        # last_price = market_value / qty (compute_open_positions doesn't surface it directly)
        last_price = Decimal(str(r.market_value)) / Decimal(str(r.qty))
        # Account label: use the first account (or the chip if available).
        account_label = r.accounts[0] if r.accounts else ""
        positions.append(
            Position(
                symbol=r.symbol,
                account_label=account_label,
                qty=Decimal(str(r.qty)),
                cost_basis=Decimal(str(r.open_cost)),
                last_price=last_price,
            )
        )
    return positions


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
    account = (account or "").strip()
    if action.lower() == "sell" and not account:
        # OOB swap into #sim-form-error; main target #sim-result gets cleared.
        return request.app.state.templates.TemplateResponse(
            request,
            "_sim_form_error.html",
            {"message": "Account is required for Sell."},
        )
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


@router.get("/sim/suggestions", response_class=HTMLResponse)
def sim_suggestions(
    request: Request,
    repo: Repository = Depends(get_repository),
    pricing: PricingService = Depends(get_pricing_service),
) -> HTMLResponse:
    """Up to three chips for the /sim page: largest loss, wash-sale risk, largest gain.

    Empty portfolio falls back to a single demo chip.
    """
    from datetime import date, timedelta

    from net_alpha.portfolio.sim_suggestions import (
        LossClose,
        top_suggestions,
    )

    today = date.today()

    positions = _build_sim_positions(repo=repo, pricing=pricing)

    # Quotes for the loss-closes block below — needs equity tickers from
    # recent sells (some of which won't appear in `positions` because they're
    # now fully closed; we still want their last price for the wash-risk chip).
    sell_tickers = {
        t.ticker
        for t in repo.all_trades()
        if t.action.lower() in {"sell", "sell to close"}
        and (today - t.date).days <= 30
        and t.option_details is None
    }
    open_tickers = {p.symbol for p in positions}
    extra = sell_tickers - open_tickers
    if extra:
        more_quotes = pricing.get_prices(sorted(extra))
        open_quotes = pricing.get_prices(sorted(open_tickers)) if open_tickers else {}
        quotes = {**open_quotes, **more_quotes}
    else:
        quotes = pricing.get_prices(sorted(open_tickers)) if open_tickers else {}

    # Recent loss closes — last 30 days, equity only.
    losses: list[LossClose] = []
    for t in repo.all_trades():
        if t.action.lower() not in {"sell", "sell to close"}:
            continue
        if t.proceeds is None or t.cost_basis is None:
            continue
        if t.option_details is not None:
            continue
        if (today - t.date).days > 30:
            continue
        pnl = Decimal(str(t.proceeds)) - Decimal(str(t.cost_basis))
        if pnl >= 0:
            continue
        q = quotes.get(t.ticker)
        last = Decimal(str(q.price)) if q is not None and q.price is not None else Decimal("0")
        losses.append(
            LossClose(
                symbol=t.ticker,
                account_label=t.account,
                closed_on=t.date,
                loss=pnl,
                lockout_clear=t.date + timedelta(days=30),
                last_price=last,
            )
        )

    chips = top_suggestions(positions, losses, today=today)
    return request.app.state.templates.TemplateResponse(
        request,
        "_sim_suggestions.html",
        {"chips": chips},
    )
