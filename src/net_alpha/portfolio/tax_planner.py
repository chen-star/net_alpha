"""Forward tax planner — harvest queue, offset budget, projection, traffic light.

All compute is pure-function over Repository / PricingService reads. No DB writes.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from net_alpha.db.repository import Repository
from net_alpha.engine.lockout import compute_lockout_clear_date
from net_alpha.models.domain import Lot, Trade
from net_alpha.portfolio.carryforward import Carryforward
from net_alpha.portfolio.positions import consume_lots_fifo
from net_alpha.pricing.service import PricingService

# §1211: capital losses can offset up to $3,000 of ordinary income per year.
# Excess flows to next year's carryforward.
ORDINARY_LOSS_CAP = Decimal("3000")

# ---------------------------------------------------------------------------
# Tax projection models (Task 15)
# ---------------------------------------------------------------------------


class MissingTaxConfig(Exception):
    """Raised by project_year_end_tax when no TaxBrackets provided."""


class TaxBrackets(BaseModel):
    """Single-marginal-rate tax inputs (loaded from config.yaml `tax:` section)."""

    filing_status: Literal["single", "mfj", "mfs", "hoh"]
    state: str  # ISO; "" for federal-only
    federal_marginal_rate: Decimal
    state_marginal_rate: Decimal
    ltcg_rate: Decimal
    qualified_div_rate: Decimal
    niit_enabled: bool = True


class TaxProjection(BaseModel):
    """Single-marginal-rate year-end estimate. NOT a tax return."""

    year: int
    realized_st_gain: Decimal  # signed
    realized_lt_gain: Decimal  # signed
    qualified_div: Decimal
    ordinary_div: Decimal
    interest_income: Decimal
    federal_tax: Decimal
    state_tax: Decimal
    total_tax: Decimal
    bracket_warnings: list[str] = []


def _classify_st_lt_gains(repo: Repository, year: int) -> tuple[Decimal, Decimal]:
    """Return (st_gain, lt_gain) — both signed, by sell-trade holding period."""
    st = Decimal("0")
    lt = Decimal("0")
    buys: dict[tuple[str, str], list[Trade]] = {}
    for t in repo.all_trades():
        if t.action.lower() in {"buy", "buy to open"} and t.option_details is None:
            buys.setdefault((t.account, t.ticker), []).append(t)
    for chain in buys.values():
        chain.sort(key=lambda x: x.date)

    for sell in repo.all_trades():
        if sell.action.lower() not in {"sell"}:
            continue
        if sell.option_details is not None:
            continue
        if sell.date.year != year:
            continue
        if sell.proceeds is None or sell.cost_basis is None:
            continue
        chain = buys.get((sell.account, sell.ticker), [])
        pnl = Decimal(str(sell.proceeds)) - Decimal(str(sell.cost_basis))
        if not chain:
            st += pnl
            continue
        oldest_buy_date = chain[0].date
        days_held = (sell.date - oldest_buy_date).days
        if days_held > LT_HOLDING_DAYS:
            lt += pnl
        else:
            st += pnl
    return st, lt


def _quantize(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"))


def project_year_end_tax(
    repo: Repository,
    year: int,
    brackets: TaxBrackets | None,
    planned_trades: list[PlannedTrade] | None = None,
) -> TaxProjection:
    if brackets is None:
        raise MissingTaxConfig("TaxBrackets required; set tax: section in config.yaml")

    st, lt = _classify_st_lt_gains(repo, year)

    # Apply planned trades (conservative: all planned trades default to ST).
    if planned_trades:
        for p in planned_trades:
            if p.action != "Sell":
                continue
            lots = repo.get_lots_for_ticker(p.symbol)
            total_qty = sum((Decimal(str(lot.quantity)) for lot in lots), Decimal("0"))
            if total_qty <= 0:
                continue
            total_basis = sum((Decimal(str(lot.adjusted_basis)) for lot in lots), Decimal("0"))
            avg_basis = total_basis / total_qty
            pnl = (p.price - avg_basis) * p.qty
            st += pnl

    qualified_div = Decimal("0")
    ordinary_div = Decimal("0")
    interest_income = Decimal("0")
    for ev in repo.list_cash_events():
        # CashEvent uses .event_date (confirmed from domain.py)
        ev_date = ev.event_date
        if ev_date is None or ev_date.year != year:
            continue
        kind = (ev.kind or "").lower()
        amt = Decimal(str(ev.amount))
        if amt <= 0:
            continue
        if "qualified" in kind:
            qualified_div += amt
        elif "dividend" in kind:
            ordinary_div += amt
        elif "interest" in kind:
            interest_income += amt

    federal = Decimal("0")
    state = Decimal("0")
    if st > 0:
        federal += st * brackets.federal_marginal_rate
        state += st * brackets.state_marginal_rate
    if lt > 0:
        federal += lt * brackets.ltcg_rate
        state += lt * brackets.state_marginal_rate
    federal += qualified_div * brackets.qualified_div_rate
    state += qualified_div * brackets.state_marginal_rate
    federal += ordinary_div * brackets.federal_marginal_rate
    state += ordinary_div * brackets.state_marginal_rate
    federal += interest_income * brackets.federal_marginal_rate
    state += interest_income * brackets.state_marginal_rate

    BRACKET_PUSH_THRESHOLD = Decimal("20000")
    warnings_list: list[str] = []
    if st >= BRACKET_PUSH_THRESHOLD:
        warnings_list.append(f"Short-term gain of ${st:,.0f} may push you into a higher federal bracket.")
    if lt >= BRACKET_PUSH_THRESHOLD:
        warnings_list.append(f"Long-term gain of ${lt:,.0f} may approach the 20% LTCG bracket boundary.")

    return TaxProjection(
        year=year,
        realized_st_gain=st,
        realized_lt_gain=lt,
        qualified_div=qualified_div,
        ordinary_div=ordinary_div,
        interest_income=interest_income,
        federal_tax=_quantize(federal),
        state_tax=_quantize(state),
        total_tax=_quantize(federal + state),
        bracket_warnings=warnings_list,
    )


LT_HOLDING_DAYS = 365  # tax long-term threshold (>365 days held)


class CSPAssigned(BaseModel):
    """Origin event for a long-stock lot acquired via cash-secured-put assignment."""

    kind: Literal["csp_assigned"] = "csp_assigned"
    option_natural_key: str  # e.g. "UUUU 09/19/2025 5.00 P"
    premium_received: Decimal
    strike: Decimal
    assignment_date: date


class CCAssigned(BaseModel):
    """Origin event for a stock SELL caused by covered-call assignment."""

    kind: Literal["cc_assigned"] = "cc_assigned"
    option_natural_key: str
    premium_received: Decimal
    strike: Decimal
    assignment_date: date


PremiumOriginEvent = CSPAssigned | CCAssigned


def _option_natural_key(t: Trade) -> str | None:
    od = t.option_details
    if od is None:
        return None
    cp = od.call_put.upper()
    return f"{t.ticker} {od.expiry.strftime('%m/%d/%Y')} {Decimal(str(od.strike)):.2f} {cp}"


def extract_premium_origin(
    lot_trade: Trade,
    all_trades: list[Trade],
) -> PremiumOriginEvent | None:
    """Recover the premium-origin event for a lot, if any.

    Looks at *lot_trade.basis_source*:
      - "option_short_open_assigned": Buy from CSP assignment. Premium = sum of STO
        proceeds minus BTC proceeds for the same option natural key, same account,
        on or before the assignment date.
      - Otherwise: returns None.
    """
    if lot_trade.basis_source != "option_short_open_assigned":
        return None

    # The synthetic Buy carries no option_details — recover them from any matching
    # STO/BTC chain by date+account+strike if the parser emitted hints, else by
    # finding the unique closed STO chain on the same date and account.
    candidates = [
        t
        for t in all_trades
        if t.account == lot_trade.account
        and t.ticker == lot_trade.ticker
        and t.option_details is not None
        and t.option_details.call_put.upper() == "P"
        and t.option_details.expiry == lot_trade.date
    ]
    if not candidates:
        return None

    # Group by option natural key; choose the chain that closes on lot_trade.date.
    by_key: dict[str, list[Trade]] = {}
    for t in candidates:
        key = _option_natural_key(t)
        if key:
            by_key.setdefault(key, []).append(t)

    chosen_key: str | None = None
    chosen_chain: list[Trade] = []
    for key, chain in by_key.items():
        has_assigned_close = any(t.basis_source == "option_short_close_assigned" for t in chain)
        if has_assigned_close:
            chosen_key = key
            chosen_chain = chain
            break

    if chosen_key is None:
        return None

    sto_proceeds = sum(
        (Decimal(str(t.proceeds)) for t in chosen_chain if t.basis_source == "option_short_open"),
        start=Decimal("0"),
    )
    btc_proceeds = sum(
        (Decimal(str(t.proceeds)) for t in chosen_chain if t.basis_source == "option_short_close_assigned"),
        start=Decimal("0"),
    )
    premium = sto_proceeds - btc_proceeds

    sample = chosen_chain[0].option_details
    assert sample is not None
    return CSPAssigned(
        option_natural_key=chosen_key,
        premium_received=premium,
        strike=Decimal(str(sample.strike)),
        assignment_date=lot_trade.date,
    )


class HarvestOpportunity(BaseModel):
    """One open lot at unrealized loss, eligible for tax-loss harvesting."""

    symbol: str
    account_id: int
    account_label: str
    qty: Decimal
    open_basis: Decimal  # remaining basis on the open lot
    loss: Decimal  # negative (open_basis - market_value, signed loss)
    lt_st: Literal["LT", "ST"]
    lockout_clear: date | None
    premium_offset: Decimal | None  # absolute amount of premium received from origin event
    premium_origin_event: PremiumOriginEvent | None
    suggested_replacements: list[str]


# ---------------------------------------------------------------------------
# Harvest queue helpers
# ---------------------------------------------------------------------------


def _account_lookup(repo: Repository) -> dict[str, int]:
    return {a.display(): a.id for a in repo.list_accounts() if a.id is not None}


def _open_lots_with_loss(
    repo: Repository,
    pricing: PricingService,
    as_of: date,
    account_id: int | None,
) -> list[tuple[Lot, Decimal, Decimal, Decimal]]:
    """Return (lot, remaining_qty, remaining_basis, market_value) for open loss lots.

    Excludes gains, options, and lots without a current price.
    """
    lots = repo.all_lots()
    trades = repo.all_trades()
    gl_eq = repo.get_equity_gl_closures()
    gl_opt = repo.get_option_gl_closures()
    consumed = consume_lots_fifo(
        lots=lots,
        trades=trades,
        gl_closures=gl_eq,
        gl_option_closures=gl_opt,
    )

    accounts = _account_lookup(repo)
    symbols = sorted({lot.ticker for (lot, qty, _basis) in consumed if qty > 0 and lot.option_details is None})
    quotes = pricing.get_prices(symbols)

    candidates: list[tuple[Lot, Decimal, Decimal, Decimal]] = []
    for lot, remaining_qty, remaining_basis in consumed:
        if remaining_qty <= 0:
            continue
        if lot.option_details is not None:
            continue
        if account_id is not None and accounts.get(lot.account) != account_id:
            continue
        quote = quotes.get(lot.ticker)
        if quote is None:
            continue
        market_value = Decimal(str(remaining_qty)) * Decimal(str(quote.price))
        if market_value >= Decimal(str(remaining_basis)):
            continue  # at gain or flat
        candidates.append((lot, Decimal(str(remaining_qty)), Decimal(str(remaining_basis)), market_value))
    return candidates


def compute_harvest_queue(
    repo: Repository,
    pricing: PricingService,
    as_of: date,
    etf_pairs: dict[str, list[str]],
    etf_replacements: dict[str, list[str]],
    account_id: int | None = None,
    only_harvestable: bool = False,
) -> list[HarvestOpportunity]:
    """Open lots at unrealized loss, sortable, with lockout-clear date and premium offset.

    Pure read. Returns rows sorted by absolute loss descending (most-negative first).
    """
    candidates = _open_lots_with_loss(repo, pricing, as_of, account_id)
    accounts = _account_lookup(repo)
    all_trades = repo.all_trades()

    rows: list[HarvestOpportunity] = []
    for lot, qty, basis, market_value in candidates:
        loss = market_value - basis
        days_held = (as_of - lot.date).days
        lt_st: Literal["LT", "ST"] = "LT" if days_held > LT_HOLDING_DAYS else "ST"
        clear = compute_lockout_clear_date(
            symbol=lot.ticker,
            account=lot.account,
            all_trades=all_trades,
            as_of=as_of,
            etf_pairs=etf_pairs,
        )
        if only_harvestable and clear is not None:
            continue

        # Premium offset: only if origin trade is a CSP-assigned synthetic Buy.
        origin_event: PremiumOriginEvent | None = None
        premium_offset: Decimal | None = None
        if lot.trade_id is not None:
            for t in all_trades:
                if t.id is not None and str(t.id) == str(lot.trade_id):
                    origin_event = extract_premium_origin(t, all_trades)
                    if origin_event is not None:
                        premium_offset = origin_event.premium_received
                    break

        rows.append(
            HarvestOpportunity(
                symbol=lot.ticker,
                account_id=accounts.get(lot.account, 0),
                account_label=lot.account,
                qty=qty,
                open_basis=basis,
                loss=loss,
                lt_st=lt_st,
                lockout_clear=clear,
                premium_offset=premium_offset,
                premium_origin_event=origin_event,
                suggested_replacements=list(etf_replacements.get(lot.ticker, [])),
            )
        )

    rows.sort(key=lambda r: r.loss)  # most-negative first
    return rows


def _realized_in_year(repo: Repository, year: int) -> tuple[Decimal, Decimal]:
    """Return (gross_losses_ytd_signed_negative, gross_gains_ytd_positive)."""
    losses = Decimal("0")
    gains = Decimal("0")
    for t in repo.all_trades():
        if t.action.lower() not in {"sell", "sell to close"}:
            continue
        if t.date.year != year:
            continue
        if t.proceeds is None or t.cost_basis is None:
            continue
        pnl = Decimal(str(t.proceeds)) - Decimal(str(t.cost_basis))
        if pnl < 0:
            losses += pnl
        else:
            gains += pnl
    return losses, gains


def _planned_pnl(planned_trades: list[PlannedTrade], repo: Repository) -> Decimal:
    """Best-effort realized delta for planned sells using avg basis from open lots."""
    delta = Decimal("0")
    for p in planned_trades:
        if p.action != "Sell":
            continue
        lots = repo.get_lots_for_ticker(p.symbol)
        total_qty = sum((Decimal(str(lot.quantity)) for lot in lots), Decimal("0"))
        if total_qty <= 0:
            continue
        total_basis = sum(
            (Decimal(str(lot.adjusted_basis)) for lot in lots),
            Decimal("0"),
        )
        avg_basis = total_basis / total_qty
        delta += (p.price - avg_basis) * p.qty
    return delta


def compute_offset_budget(
    repo: Repository,
    year: int,
    planned_trades: list[PlannedTrade] | None = None,
    carryforward: Carryforward | None = None,
) -> OffsetBudget:
    """YTD realized P&L vs the $3,000-against-ordinary cap, optionally with planned trades.

    Pure read. Cap is fixed at $3,000.

    When ``carryforward`` is supplied, the prior-year ST/LT loss carryforward is
    folded into the projection: the combined (current-year net loss + incoming
    carryforward) is what gets clamped at the $3K ordinary-income cap, with the
    residue surfaced as ``carryforward_projection`` (the amount that will roll
    forward into the next year).
    """
    losses, gains = _realized_in_year(repo, year)
    net = losses + gains

    cf_st = carryforward.st if carryforward else Decimal("0")
    cf_lt = carryforward.lt if carryforward else Decimal("0")
    cf_total = cf_st + cf_lt

    cap = ORDINARY_LOSS_CAP
    used = Decimal("0")
    carry = Decimal("0")

    # Prior carryforward + this year's net loss combine; the $3K cap applies.
    total_loss_with_cf = max(Decimal("0"), -net) + cf_total
    if total_loss_with_cf > 0:
        used = min(total_loss_with_cf, cap)
        carry = max(total_loss_with_cf - cap, Decimal("0"))

    planned_delta = _planned_pnl(planned_trades or [], repo)

    return OffsetBudget(
        year=year,
        realized_losses_ytd=losses,
        realized_gains_ytd=gains,
        net_realized=net,
        cap_against_ordinary=cap,
        used_against_ordinary=used,
        carryforward_projection=carry,
        planned_delta=planned_delta,
        incoming_carryforward_st=cf_st,
        incoming_carryforward_lt=cf_lt,
    )


class PlannedTrade(BaseModel):
    """Transient struct: a hypothetical sell/buy that hasn't been imported yet.

    Used by the harvest queue 'Mark planned' action and by the traffic light.
    Stored only in the user's localStorage for the session.
    """

    symbol: str
    account_id: int
    action: Literal["Buy", "Sell"]
    qty: Decimal
    price: Decimal
    on: date


class OffsetBudget(BaseModel):
    """YTD realized loss vs the $3,000-against-ordinary-income cap."""

    year: int
    realized_losses_ytd: Decimal  # signed (negative magnitude)
    realized_gains_ytd: Decimal  # positive
    net_realized: Decimal  # gains + losses (signed)
    cap_against_ordinary: Decimal = ORDINARY_LOSS_CAP
    used_against_ordinary: Decimal  # min(|net_loss|, cap), >= 0
    carryforward_projection: Decimal  # |net_loss| - cap, clamped to >= 0
    planned_delta: Decimal  # change in net_realized that would result from planned_trades
    # Incoming prior-year ST/LT capital-loss carryforward magnitudes (positive
    # numbers; zero when no carryforward is supplied or available).
    incoming_carryforward_st: Decimal = Decimal("0")
    incoming_carryforward_lt: Decimal = Decimal("0")


# ---------------------------------------------------------------------------
# Traffic-light signal (Task 19-21)
# ---------------------------------------------------------------------------


class TaxLightSignal(BaseModel):
    """Traffic-light verdict for a hypothetical trade."""

    color: Literal["green", "yellow", "red"]
    reason_codes: list[str]
    explanation: str
    suggestion: str | None
    lot_method_recommended: Literal["FIFO", "HIFO", "LIFO"] | None


def _avg_basis(repo: Repository, symbol: str) -> Decimal | None:
    lots = repo.get_lots_for_ticker(symbol)
    total_qty = sum((Decimal(str(lot.quantity)) for lot in lots), Decimal("0"))
    if total_qty <= 0:
        return None
    total_basis = sum((Decimal(str(lot.adjusted_basis)) for lot in lots), Decimal("0"))
    return total_basis / total_qty


def assess_trade(
    proposed: PlannedTrade,
    repo: Repository,
    brackets: TaxBrackets | None,
    as_of: date,
    etf_pairs: dict[str, list[str]],
) -> TaxLightSignal:
    """Pre-trade traffic-light: green/yellow/red verdict with explanation."""
    if proposed.action != "Sell":
        return TaxLightSignal(
            color="green",
            reason_codes=["BUY"],
            explanation="Buy trades aren't tax-blocking on the sell side.",
            suggestion=None,
            lot_method_recommended=None,
        )

    avg_basis = _avg_basis(repo, proposed.symbol)
    pnl_per_share = (proposed.price - avg_basis) if avg_basis is not None else None
    is_loss = pnl_per_share is not None and pnl_per_share < 0

    if is_loss:
        clear = compute_lockout_clear_date(
            symbol=proposed.symbol,
            account="",
            all_trades=repo.all_trades(),
            as_of=as_of,
            etf_pairs=etf_pairs,
        )
        if clear is not None and clear > as_of:
            return TaxLightSignal(
                color="red",
                reason_codes=["WASH_RISK"],
                explanation=(
                    f"Selling at a loss today triggers wash-sale lockout until "
                    f"{clear.isoformat()} due to a recent qualifying buy."
                ),
                suggestion=f"Delay sell until {clear.isoformat()} to avoid the lockout.",
                lot_method_recommended=None,
            )

    days_held: int | None = None
    if avg_basis is not None:
        lots = repo.get_lots_for_ticker(proposed.symbol)
        if lots:
            oldest = min(lots, key=lambda lot: lot.date).date
            days_held = (as_of - oldest).days

    if pnl_per_share is not None and pnl_per_share > 0:
        gain = pnl_per_share * proposed.qty
        is_st = days_held is not None and days_held <= LT_HOLDING_DAYS
        BRACKET_PUSH_THRESHOLD = Decimal("20000")
        if gain >= BRACKET_PUSH_THRESHOLD and is_st and brackets is not None:
            return TaxLightSignal(
                color="yellow",
                reason_codes=["ST_GAIN_BRACKET_PUSH"],
                explanation=(
                    f"Proposed sale would create a ${gain:,.0f} short-term gain "
                    "— may push you into a higher federal bracket."
                ),
                suggestion="Consider holding past the long-term threshold to switch to LTCG rate.",
                lot_method_recommended="FIFO",
            )

    return TaxLightSignal(
        color="green",
        reason_codes=["CLEAR"],
        explanation="No wash-sale risk detected for this proposed sale.",
        suggestion=None,
        lot_method_recommended="HIFO" if is_loss else None,
    )


# ---------------------------------------------------------------------------
# Harvest plan builder (PR #2 of pre-launch UX polish)
# ---------------------------------------------------------------------------


class HarvestPlan(BaseModel):
    """Output of build_plan: selected candidates + summary math."""

    selected: list[HarvestOpportunity]
    skipped_locked: list[HarvestOpportunity]
    realized_gains_ytd: Decimal
    ordinary_offset_used: Decimal
    gain_offset_used: Decimal
    total_loss_harvested: Decimal
    estimated_tax_saved: Decimal
    target_budget: Decimal
    used_auto_budget: bool


def _tax_saved_for(opp: HarvestOpportunity, rates: TaxBrackets | None) -> Decimal:
    abs_loss = abs(opp.loss)
    if rates is None:
        return abs_loss
    if opp.lt_st == "ST":
        rate = rates.federal_marginal_rate + rates.state_marginal_rate
    else:
        rate = rates.ltcg_rate
    return abs_loss * rate


def build_plan(
    candidates: list[HarvestOpportunity],
    realized_gains_ytd: Decimal,
    marginal_rates: TaxBrackets | None,
    target_budget: Decimal | None = None,
    exclude_locked: bool = True,
) -> HarvestPlan:
    """Greedy by estimated tax saved per candidate, ST-first on ties."""
    used_auto = target_budget is None
    if target_budget is not None:
        target = target_budget
    else:
        target = max(Decimal("0"), realized_gains_ytd) + ORDINARY_LOSS_CAP

    skipped_locked: list[HarvestOpportunity] = []
    pool: list[HarvestOpportunity] = []
    for c in candidates:
        if exclude_locked and c.lockout_clear is not None:
            skipped_locked.append(c)
        else:
            pool.append(c)

    pool.sort(key=lambda c: (-_tax_saved_for(c, marginal_rates), 0 if c.lt_st == "ST" else 1))

    selected: list[HarvestOpportunity] = []
    total_loss = Decimal("0")
    tax_saved_sum = Decimal("0")
    for c in pool:
        next_total = total_loss + abs(c.loss)
        if next_total > target:
            break
        selected.append(c)
        total_loss = next_total
        tax_saved_sum += _tax_saved_for(c, marginal_rates)

    cap = ORDINARY_LOSS_CAP
    excess_over_gains = max(Decimal("0"), total_loss - max(Decimal("0"), realized_gains_ytd))
    ordinary_offset = min(cap, excess_over_gains)
    gain_offset = total_loss - ordinary_offset

    return HarvestPlan(
        selected=selected,
        skipped_locked=skipped_locked,
        realized_gains_ytd=realized_gains_ytd,
        ordinary_offset_used=ordinary_offset,
        gain_offset_used=gain_offset,
        total_loss_harvested=total_loss,
        estimated_tax_saved=tax_saved_sum,
        target_budget=target,
        used_auto_budget=used_auto,
    )


def summarize_manual_picks(
    picks: list[tuple[str, str]],
    candidates: list[HarvestOpportunity],
    realized_gains_ytd: Decimal,
    marginal_rates: TaxBrackets | None,
) -> HarvestPlan:
    """Build a HarvestPlan from an explicit (symbol, account_label) selection.

    No algorithm — the user's UI selection is authoritative. Unknown picks
    (stale UI state) are silently dropped.
    """
    by_key = {(c.symbol, c.account_label): c for c in candidates}
    selected = [by_key[k] for k in picks if k in by_key]

    total_loss = sum((abs(c.loss) for c in selected), Decimal("0"))
    tax_saved_sum = sum(
        (_tax_saved_for(c, marginal_rates) for c in selected),
        Decimal("0"),
    )
    cap = ORDINARY_LOSS_CAP
    excess_over_gains = max(Decimal("0"), total_loss - max(Decimal("0"), realized_gains_ytd))
    ordinary_offset = min(cap, excess_over_gains)
    gain_offset = total_loss - ordinary_offset

    return HarvestPlan(
        selected=selected,
        skipped_locked=[],
        realized_gains_ytd=realized_gains_ytd,
        ordinary_offset_used=ordinary_offset,
        gain_offset_used=gain_offset,
        total_loss_harvested=total_loss,
        estimated_tax_saved=tax_saved_sum,
        target_budget=total_loss,
        used_auto_budget=False,
    )
