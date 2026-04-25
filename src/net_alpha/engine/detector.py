from __future__ import annotations

from net_alpha.engine.matcher import get_match_confidence, is_within_wash_sale_window
from net_alpha.models.domain import DetectionResult, Lot, Trade, WashSaleViolation


def detect_wash_sales(
    trades: list[Trade],
    etf_pairs: dict[str, list[str]],
) -> DetectionResult:
    """Detect wash sales across all trades. Pure function — no I/O.

    Algorithm:
    1. Find all loss sales, sorted by date
    2. Create lots from all buy trades
    3. For each loss sale, match against candidates in FIFO order
    4. Allocate disallowed loss and adjust replacement lot basis
    """
    loss_sales = sorted(
        [t for t in trades if t.is_loss()],
        key=lambda t: t.date,
    )

    # Create lots from buys — track remaining allocable quantity per lot
    lots: dict[str, Lot] = {}
    lot_remaining: dict[str, float] = {}
    for t in trades:
        if t.is_buy():
            lot = Lot.from_trade(t)
            lots[t.id] = lot
            lot_remaining[t.id] = t.quantity

    # Count basis_unknown trades for the warning
    basis_unknown_count = sum(1 for t in trades if t.basis_unknown)

    violations: list[WashSaleViolation] = []

    for loss_sale in loss_sales:
        remaining_qty = loss_sale.quantity
        loss_per_unit = loss_sale.loss_amount() / loss_sale.quantity

        # Find candidates within window, sorted by date (FIFO)
        candidates = _find_candidates(loss_sale, trades, etf_pairs)

        for candidate, confidence in candidates:
            if remaining_qty <= 0:
                break

            # Determine allocable quantity
            if candidate.is_buy() and candidate.id in lot_remaining:
                available = lot_remaining[candidate.id]
                if available <= 0:
                    continue
                allocable = min(remaining_qty, available)
                lot_remaining[candidate.id] -= allocable
            elif candidate.is_sell() and candidate.is_option() and candidate.option_details.call_put == "P":
                # Sold put — no lot, use candidate quantity directly
                allocable = min(remaining_qty, candidate.quantity)
            else:
                continue

            disallowed = round(allocable * loss_per_unit, 2)

            violations.append(
                WashSaleViolation(
                    loss_trade_id=loss_sale.id,
                    replacement_trade_id=candidate.id,
                    confidence=confidence,
                    disallowed_loss=disallowed,
                    matched_quantity=allocable,
                    loss_account=loss_sale.account,
                    buy_account=candidate.account,
                    loss_sale_date=loss_sale.date,
                    triggering_buy_date=candidate.date,
                )
            )

            # Adjust replacement lot basis
            if candidate.id in lots:
                lots[candidate.id].adjusted_basis += disallowed

            remaining_qty -= allocable

    return DetectionResult(
        violations=violations,
        lots=list(lots.values()),
        basis_unknown_count=basis_unknown_count,
    )


def _find_candidates(
    loss_sale: Trade,
    all_trades: list[Trade],
    etf_pairs: dict[str, list[str]],
) -> list[tuple[Trade, str]]:
    """Find and sort candidate triggers for a loss sale.

    Returns (trade, confidence) pairs in FIFO order.
    """
    candidates: list[tuple[Trade, str]] = []
    for t in all_trades:
        if t.id == loss_sale.id:
            continue
        if not is_within_wash_sale_window(loss_sale.date, t.date):
            continue
        confidence = get_match_confidence(loss_sale, t, etf_pairs)
        if confidence is not None:
            candidates.append((t, confidence))
    candidates.sort(key=lambda x: x[0].date)
    return candidates
