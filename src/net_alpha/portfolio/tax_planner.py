"""Forward tax planner — harvest queue, offset budget, projection, traffic light.

All compute is pure-function over Repository / PricingService reads. No DB writes.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from net_alpha.models.domain import Trade


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
