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
    """One lot consumed (fully or partially) by a hypothetical sell.

    ``adjusted_basis`` is **per-share** — i.e., the source lot's adjusted
    basis divided by its original quantity. The domain ``Lot.adjusted_basis``
    is total-basis (see ``engine.detector`` which adds disallowed losses to
    the total), so ``_consume`` divides by ``lot.quantity`` when populating
    this field. P&L is therefore ``qty_consumed * (sell_price - adjusted_basis)``
    and stays correct for partial fills.
    """

    lot_id: str
    acquired_date: date
    qty_consumed: Decimal
    adjusted_basis: Decimal  # per-share (see class docstring)
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

    # Wash-sale check (Task 13). Each loss-pick is checked against the trade
    # history for substantially-identical buys within the ±30-day window. When
    # one is found, the loss magnitude is added to ``wash_sale_disallowed``
    # (rolled into the replacement lot's basis under §1091 in real recompute).
    ticker = lots[0].ticker if lots else ""
    wash_disallowed = Decimal("0")
    has_wash = False
    for p in picks:
        d = _check_wash_sale(
            p,
            sell_price=sell_price,
            sell_date=sell_date,
            ticker=ticker,
            repo=repo,
            etf_pairs=etf_pairs,
        )
        wash_disallowed += d
        if d > 0:
            has_wash = True
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

    HIFO sorts on basis-per-share, not total basis. All orderings tiebreak
    by lot_id ascending for determinism.
    """
    if strategy == "FIFO":
        return sorted(lots, key=lambda lot: (lot.date, lot.id))
    if strategy == "LIFO":
        return sorted(lots, key=lambda lot: (lot.date, lot.id), reverse=True)
    if strategy == "HIFO":

        def _per_share_basis(lot: Lot) -> Decimal:
            qty = Decimal(str(lot.quantity))
            if qty == 0:
                return Decimal("0")
            return Decimal(str(lot.adjusted_basis)) / qty

        return sorted(lots, key=lambda lot: (-_per_share_basis(lot), lot.id))
    return sorted(lots, key=lambda lot: (lot.date, lot.id))  # MIN_TAX/MAX_LOSS placeholder


def _consume(
    lots: list[Lot],
    qty: Decimal,
    sell_date: date,
) -> list[LotPick]:
    """Greedily consume the requested qty from the ordered lot list.

    Note: ``LotPick.adjusted_basis`` is stored **per-share** so partial fills
    compute correct P&L. The source ``Lot.adjusted_basis`` is total-basis
    (see ``engine.detector``), so we divide by ``lot.quantity`` here.
    """
    remaining = qty
    picks: list[LotPick] = []
    for lot in lots:
        if remaining <= 0:
            break
        lot_qty = Decimal(str(lot.quantity))
        take = min(lot_qty, remaining)
        held = (sell_date - lot.date).days
        per_share_basis = Decimal(str(lot.adjusted_basis)) / lot_qty if lot_qty else Decimal("0")
        picks.append(
            LotPick(
                lot_id=lot.id,
                acquired_date=lot.date,
                qty_consumed=take,
                adjusted_basis=per_share_basis,
                holding_period_days=held,
                is_long_term=held > LT_HOLDING_DAYS,
            )
        )
        remaining -= take
    return picks


def _check_wash_sale(
    pick: LotPick,
    *,
    sell_price: Decimal,
    sell_date: date,
    ticker: str,
    repo,
    etf_pairs: dict,
) -> Decimal:
    """Return the loss magnitude that would be disallowed (>=0). 0 = no wash.

    A pick triggers a wash sale only if (a) it would close at a loss and
    (b) there is at least one substantially-identical buy in the trade
    history within ±30 days of ``sell_date``. Substantially-identical here
    means same ticker OR within the same ETF group from ``etf_pairs``. We
    skip option buys — wash-sale equivalence between equity and option
    positions is handled by the full ``engine.detector`` pipeline; the
    pre-trade simulator stays equity-only on this side to avoid over-
    flagging hypothetical sells against unrelated covered-call buys.
    """
    pnl = pick.qty_consumed * (sell_price - pick.adjusted_basis)
    if pnl >= 0:
        return Decimal("0")  # only losses can be washed

    related = {ticker}
    for group in etf_pairs.values():
        if ticker in group:
            related.update(group)

    if repo is None:
        return Decimal("0")

    for sym in related:
        for trade in repo.trades_for_ticker_in_window(sym, sell_date, days=30):
            if not trade.is_buy():
                continue
            if trade.option_details is not None:
                continue
            if trade.basis_source.startswith("transfer_"):
                continue
            return -pnl  # disallowed loss = magnitude of the loss

    return Decimal("0")
