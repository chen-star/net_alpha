"""Best-lot picker for the Sim page. Pure function over a lot list.

Five strategies: FIFO, LIFO, HIFO, MIN_TAX, MAX_LOSS. All share the same
output shape (LotPickResult) so the Sim comparison table can render any of
them uniformly. Wash-sale awareness routes through engine.detector.

FIFO/LIFO/HIFO are pure orderings handled by ``_order_lots`` + ``_consume``.
MIN_TAX and MAX_LOSS are not orderings — they pick the *combination* of lots
that optimizes a score (after-tax P&L for MIN_TAX, pre-tax P&L for MAX_LOSS).
For ≤``GREEDY_THRESHOLD`` lots they brute-force all combos; beyond that they
fall back to a greedy heuristic (HIFO ordering) and emit an "approximate"
note so the UI can flag the result.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from net_alpha.models.domain import Lot

LT_HOLDING_DAYS = 365  # held > 365 days → long-term
GREEDY_THRESHOLD = 12  # combos beyond this fall back to greedy

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

    FIFO/LIFO/HIFO are pure orderings: lots are sorted then consumed in order.
    MIN_TAX/MAX_LOSS dispatch to ``_select_combo`` which brute-forces small
    pools and falls back to a greedy heuristic beyond ``GREEDY_THRESHOLD``.
    """
    total_avail = sum((Decimal(str(lot.quantity)) for lot in lots), Decimal("0"))
    if total_avail < qty:
        raise InsufficientLotsError(f"requested {qty} but only {total_avail} available")

    if strategy in ("MIN_TAX", "MAX_LOSS"):
        return _select_combo(
            lots=lots,
            qty=qty,
            sell_price=sell_price,
            sell_date=sell_date,
            strategy=strategy,
            repo=repo,
            etf_pairs=etf_pairs,
            brackets=brackets,
            carryforward=carryforward,
        )

    ordered = _order_lots(lots, strategy)
    picks = _consume(ordered, qty, sell_date)
    return _evaluate(
        strategy=strategy,
        picks=picks,
        sell_price=sell_price,
        sell_date=sell_date,
        ticker=lots[0].ticker if lots else "",
        repo=repo,
        etf_pairs=etf_pairs,
        brackets=brackets,
        carryforward=carryforward,
    )


def _evaluate(
    *,
    strategy: Strategy,
    picks: list[LotPick],
    sell_price: Decimal,
    sell_date: date,
    ticker: str,
    repo,
    etf_pairs: dict,
    brackets,
    carryforward,
) -> LotPickResult:
    """Compose the LotPickResult from a finalized list of picks."""
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

    after_tax, notes = _compute_after_tax(
        st=st,
        lt=lt,
        wash_disallowed=wash_disallowed,
        carryforward=carryforward,
        brackets=brackets,
        strategy=strategy,
    )

    return LotPickResult(
        strategy=strategy,
        picks=picks,
        pre_tax_pnl=pre_tax,
        st_pnl=st,
        lt_pnl=lt,
        wash_sale_disallowed=wash_disallowed,
        after_tax_pnl=after_tax,
        has_wash_sale_risk=has_wash,
        notes=notes,
    )


def _select_combo(
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
    """For MIN_TAX/MAX_LOSS — enumerate combos when feasible, greedy beyond."""
    if len(lots) <= GREEDY_THRESHOLD:
        return _select_brute(
            lots=lots,
            qty=qty,
            sell_price=sell_price,
            sell_date=sell_date,
            strategy=strategy,
            repo=repo,
            etf_pairs=etf_pairs,
            brackets=brackets,
            carryforward=carryforward,
        )
    return _select_greedy(
        lots=lots,
        qty=qty,
        sell_price=sell_price,
        sell_date=sell_date,
        strategy=strategy,
        repo=repo,
        etf_pairs=etf_pairs,
        brackets=brackets,
        carryforward=carryforward,
    )


def _select_brute(
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
    """Brute-force: try every subset (smallest first) that covers qty.

    Iteration starts at 1-lot combos and grows; combined with stable lot_id
    sorting this naturally prefers fewer-lot, deterministic solutions on ties.
    """
    from itertools import combinations

    best: LotPickResult | None = None
    sorted_lots = sorted(lots, key=lambda lot: lot.id)
    ticker = lots[0].ticker if lots else ""
    for r in range(1, len(sorted_lots) + 1):
        for combo in combinations(sorted_lots, r):
            combo_qty = sum((Decimal(str(lot.quantity)) for lot in combo), Decimal("0"))
            if combo_qty < qty:
                continue
            picks = _consume(list(combo), qty, sell_date)
            cand = _evaluate(
                strategy=strategy,
                picks=picks,
                sell_price=sell_price,
                sell_date=sell_date,
                ticker=ticker,
                repo=repo,
                etf_pairs=etf_pairs,
                brackets=brackets,
                carryforward=carryforward,
            )
            if best is None or _is_better(cand, best, strategy):
                best = cand
    assert best is not None  # total_avail >= qty guaranteed by caller
    return best


def _is_better(a: LotPickResult, b: LotPickResult, strategy: Strategy) -> bool:
    """Strategy-specific scoring for combo enumeration.

    MIN_TAX picks the combo with the smallest *tax bill on this transaction*
    — i.e., it maximizes the tax delta ``(after_tax_pnl - pre_tax_pnl)``,
    which captures how much tax this sale saves (positive = refund, negative
    = tax owed). Comparing ``after_tax_pnl`` directly would conflate trade
    economics with tax outcome and pick the gain over the loss every time;
    a tax-aware planner wants the loss so the user banks the deduction.

    MAX_LOSS minimizes pre-tax P&L (most negative loss). Both strategies
    prefer combos with no wash-sale risk on ties.
    """
    if strategy == "MIN_TAX":
        a_savings = a.after_tax_pnl - a.pre_tax_pnl
        b_savings = b.after_tax_pnl - b.pre_tax_pnl
        if a_savings != b_savings:
            return a_savings > b_savings
        if a.has_wash_sale_risk != b.has_wash_sale_risk:
            return not a.has_wash_sale_risk
        return False
    if strategy == "MAX_LOSS":
        if a.pre_tax_pnl != b.pre_tax_pnl:
            return a.pre_tax_pnl < b.pre_tax_pnl
        if a.has_wash_sale_risk != b.has_wash_sale_risk:
            return not a.has_wash_sale_risk
        return False
    return False


def _select_greedy(
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
    """Greedy fallback for >GREEDY_THRESHOLD lots.

    Both MIN_TAX and MAX_LOSS use HIFO ordering as a heuristic — highest
    per-share basis first maximizes the loss (or minimizes the gain) per
    pick, which is a decent proxy for "lowest tax bill" and a direct match
    for "biggest loss." An "approximate" note is appended so the UI can
    surface that exact search was skipped.
    """
    ordered = _order_lots(lots, "HIFO")
    picks = _consume(ordered, qty, sell_date)
    result = _evaluate(
        strategy=strategy,
        picks=picks,
        sell_price=sell_price,
        sell_date=sell_date,
        ticker=lots[0].ticker if lots else "",
        repo=repo,
        etf_pairs=etf_pairs,
        brackets=brackets,
        carryforward=carryforward,
    )
    result.notes.append(f"Approximate (greedy): exact search disabled for >{GREEDY_THRESHOLD} lots")
    return result


def _order_lots(lots: list[Lot], strategy: Strategy) -> list[Lot]:
    """Return lots in consumption order for the given strategy.

    Only FIFO/LIFO/HIFO are valid here — MIN_TAX/MAX_LOSS go through
    ``_select_combo`` and never reach this function. HIFO sorts on
    basis-per-share, not total basis. All orderings tiebreak by lot_id
    ascending for determinism.
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
    # Defensive: should not be reached — MIN_TAX/MAX_LOSS go through _select_combo.
    return sorted(lots, key=lambda lot: (lot.date, lot.id))


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


def _compute_after_tax(
    *,
    st: Decimal,
    lt: Decimal,
    wash_disallowed: Decimal,
    carryforward,
    brackets,
    strategy: Strategy,
) -> tuple[Decimal, list[str]]:
    """Apply carryforward absorption + brackets + $3K cap.

    Disallowed losses contribute $0 current-year benefit (the loss is rolled
    into the replacement lot's basis under §1091, not realized this year).
    """
    notes: list[str] = []
    pre_tax = st + lt

    if brackets is None:
        if strategy == "MIN_TAX":
            notes.append("Min Tax disabled — no tax brackets configured")
        return pre_tax, notes

    # Strip disallowed loss out of the deductible side. Allocate proportionally
    # to whichever bucket(s) had losses.
    if wash_disallowed > 0:
        total_loss = max(Decimal("0"), -st) + max(Decimal("0"), -lt)
        if total_loss > 0:
            st_disallow = (max(Decimal("0"), -st) / total_loss) * wash_disallowed
            lt_disallow = (max(Decimal("0"), -lt) / total_loss) * wash_disallowed
            st = st + st_disallow  # less negative (closer to 0)
            lt = lt + lt_disallow

    # Apply carryforward (carryforward magnitudes are positive numbers).
    cf_st = carryforward.st if carryforward else Decimal("0")
    cf_lt = carryforward.lt if carryforward else Decimal("0")
    st_after = st - cf_st
    lt_after = lt - cf_lt

    # Cross-category netting if one is negative and the other positive.
    if st_after < 0 and lt_after > 0:
        absorbed = min(-st_after, lt_after)
        st_after += absorbed
        lt_after -= absorbed
    elif lt_after < 0 and st_after > 0:
        absorbed = min(-lt_after, st_after)
        lt_after += absorbed
        st_after -= absorbed

    # Tax on positive side; losses give tax benefit only via $3K cap.
    st_tax = max(Decimal("0"), st_after) * brackets.federal_marginal_rate
    lt_tax = max(Decimal("0"), lt_after) * brackets.ltcg_rate
    state_tax = max(Decimal("0"), st_after + lt_after) * brackets.state_marginal_rate
    tax_bill = st_tax + lt_tax + state_tax

    # Loss residue: up to $3K against ordinary saves federal_marginal_rate * $3K.
    loss_residue = max(Decimal("0"), -(st_after + lt_after))
    cap_used = min(loss_residue, Decimal("3000"))
    loss_benefit = cap_used * brackets.federal_marginal_rate

    after_tax = pre_tax - tax_bill + loss_benefit
    return after_tax, notes
