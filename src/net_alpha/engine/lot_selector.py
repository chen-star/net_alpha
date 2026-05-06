"""Best-lot picker for the Sim page. Pure function over a lot list.

Five strategies: FIFO, LIFO, HIFO, MIN_TAX, MAX_LOSS. All share the same
output shape (LotPickResult) so the Sim comparison table can render any of
them uniformly. Wash-sale awareness routes through engine.detector.

This file ships the skeleton + FIFO/LIFO/HIFO ordering. Tasks 12-16 extend
with wash-sale checks, after-tax math, MIN_TAX combo enumeration, and
MAX_LOSS strategy.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from net_alpha.models.domain import Lot

LT_HOLDING_DAYS = 365  # held > 365 days → long-term

Strategy = Literal["FIFO", "LIFO", "HIFO", "MIN_TAX", "MAX_LOSS"]


class InsufficientLotsError(ValueError):
    """Raised when total lot qty < requested sell qty."""


class LotPick(BaseModel):
    lot_id: str
    acquired_date: date
    qty_consumed: Decimal
    adjusted_basis: Decimal
    holding_period_days: int
    is_long_term: bool


class LotPickResult(BaseModel):
    strategy: Strategy
    picks: list[LotPick]
    pre_tax_pnl: Decimal
    st_pnl: Decimal
    lt_pnl: Decimal
    wash_sale_disallowed: Decimal
    after_tax_pnl: Decimal
    has_wash_sale_risk: bool
    notes: list[str] = Field(default_factory=list)


def select_lots(
    *,
    lots: list[Lot],
    qty: Decimal,
    sell_price: Decimal,
    sell_date: date,
    strategy: Strategy,
    repo,
    etf_pairs: dict,
    brackets,
    carryforward,
) -> LotPickResult:
    """Pick lots for a hypothetical sell, returning a fully-populated result.

    This skeleton implementation handles FIFO/LIFO/HIFO ordering. Wash-sale
    check, after-tax math, and the MIN_TAX/MAX_LOSS strategies land in
    subsequent tasks. The ``repo``, ``etf_pairs``, ``brackets``, and
    ``carryforward`` parameters are accepted for forward compatibility and
    intentionally unused at this stage.
    """
    total_avail = sum((Decimal(str(lot.quantity)) for lot in lots), Decimal("0"))
    if total_avail < qty:
        raise InsufficientLotsError(f"requested {qty} but only {total_avail} available")

    ordered = _order_lots(lots, strategy)
    picks = _consume(ordered, qty, sell_date)

    pre_tax = sum(
        (p.qty_consumed * (sell_price - p.adjusted_basis) for p in picks),
        Decimal("0"),
    )
    st = sum(
        (p.qty_consumed * (sell_price - p.adjusted_basis) for p in picks if not p.is_long_term),
        Decimal("0"),
    )
    lt = sum(
        (p.qty_consumed * (sell_price - p.adjusted_basis) for p in picks if p.is_long_term),
        Decimal("0"),
    )

    # Tasks 13/14 add wash-sale check + after-tax math. Skeleton: zeros.
    wash_disallowed = Decimal("0")
    has_wash = False
    after_tax = pre_tax  # placeholder until brackets applied in Task 14

    return LotPickResult(
        strategy=strategy,
        picks=picks,
        pre_tax_pnl=pre_tax,
        st_pnl=st,
        lt_pnl=lt,
        wash_sale_disallowed=wash_disallowed,
        after_tax_pnl=after_tax,
        has_wash_sale_risk=has_wash,
    )


def _order_lots(lots: list[Lot], strategy: Strategy) -> list[Lot]:
    """Return lots in consumption order for the given strategy.

    MIN_TAX and MAX_LOSS are NOT pure orderings — Tasks 15/16 implement them
    with combo enumeration. For now they fall through to FIFO (skeleton).
    """
    if strategy == "FIFO":
        return sorted(lots, key=lambda lot: lot.date)
    if strategy == "LIFO":
        return sorted(lots, key=lambda lot: lot.date, reverse=True)
    if strategy == "HIFO":
        return sorted(lots, key=lambda lot: -Decimal(str(lot.adjusted_basis)))
    return sorted(lots, key=lambda lot: lot.date)  # placeholder for MIN_TAX/MAX_LOSS


def _consume(
    lots: list[Lot],
    qty: Decimal,
    sell_date: date,
) -> list[LotPick]:
    """Greedily consume the requested qty from the ordered lot list."""
    remaining = qty
    picks: list[LotPick] = []
    for lot in lots:
        if remaining <= 0:
            break
        lot_qty = Decimal(str(lot.quantity))
        take = min(lot_qty, remaining)
        held = (sell_date - lot.date).days
        picks.append(
            LotPick(
                lot_id=lot.id,
                acquired_date=lot.date,
                qty_consumed=take,
                adjusted_basis=Decimal(str(lot.adjusted_basis)),
                holding_period_days=held,
                is_long_term=held > LT_HOLDING_DAYS,
            )
        )
        remaining -= take
    return picks
