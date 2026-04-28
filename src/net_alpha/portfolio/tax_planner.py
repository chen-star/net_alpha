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
from net_alpha.portfolio.positions import consume_lots_fifo
from net_alpha.pricing.service import PricingService

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
    cap_against_ordinary: Decimal = Decimal("3000")
    used_against_ordinary: Decimal  # min(|net_loss|, cap), >= 0
    carryforward_projection: Decimal  # |net_loss| - cap, clamped to >= 0
    planned_delta: Decimal  # change in net_realized that would result from planned_trades
