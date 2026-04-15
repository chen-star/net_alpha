from __future__ import annotations

from collections import defaultdict
from datetime import date

from net_alpha.models.domain import (
    AllocationResult,
    LotRecommendation,
    LotSelection,
    OpenLot,
    RealizedPair,
    TaxPosition,
    Trade,
)


def _allocate_lots(trades: list[Trade], as_of: date) -> AllocationResult:
    """Replay per-(account, ticker) FIFO allocation.

    Returns realized pairs (sell matched to buy) and remaining open lots.
    Options are excluded from open lots.
    """
    # Group trades by (account, ticker)
    groups: dict[tuple[str, str], list[Trade]] = defaultdict(list)
    for t in trades:
        groups[(t.account, t.ticker)].append(t)

    all_realized: list[RealizedPair] = []
    all_open: list[OpenLot] = []

    for (account, ticker), group_trades in groups.items():
        # Sort by (date, id) for deterministic FIFO
        group_trades.sort(key=lambda t: (t.date, t.id))

        # Build buy queue: list of [trade, remaining_qty, remaining_basis]
        buy_queue: list[list] = []
        sells: list[Trade] = []

        for t in group_trades:
            if t.is_buy():
                buy_queue.append([t, t.quantity, t.cost_basis or 0.0])
            elif t.is_sell():
                sells.append(t)

        # Process sells in date order (already sorted)
        for sell in sells:
            remaining_sell_qty = sell.quantity

            for entry in buy_queue:
                if remaining_sell_qty <= 0:
                    break

                buy_trade, buy_remaining_qty, buy_remaining_basis = entry
                if buy_remaining_qty <= 0:
                    continue

                consumed = min(remaining_sell_qty, buy_remaining_qty)
                basis_per_share = buy_remaining_basis / buy_remaining_qty if buy_remaining_qty > 0 else 0.0
                consumed_basis = round(consumed * basis_per_share, 2)
                consumed_proceeds = round((sell.proceeds or 0.0) * consumed / sell.quantity, 2)

                holding_days = (sell.date - buy_trade.date).days
                is_lt = holding_days > 365

                all_realized.append(
                    RealizedPair(
                        sell_trade_id=sell.id,
                        buy_lot_date=buy_trade.date,
                        buy_lot_account=account,
                        quantity=consumed,
                        proceeds=consumed_proceeds,
                        basis=consumed_basis,
                        basis_unknown=buy_trade.basis_unknown,
                        is_long_term=is_lt,
                    )
                )

                entry[1] -= consumed  # remaining_qty
                entry[2] -= consumed_basis  # remaining_basis
                remaining_sell_qty -= consumed

        # Remaining buys become open lots (skip options)
        for entry in buy_queue:
            buy_trade, remaining_qty, remaining_basis = entry
            if remaining_qty <= 0:
                continue
            if buy_trade.is_option():
                continue

            holding_days = (as_of - buy_trade.date).days
            days_to_lt = max(0, 366 - holding_days)

            all_open.append(
                OpenLot(
                    ticker=ticker,
                    account=account,
                    quantity=remaining_qty,
                    adjusted_basis_per_share=round(remaining_basis / remaining_qty, 2) if remaining_qty > 0 else 0.0,
                    purchase_date=buy_trade.date,
                    days_held=holding_days,
                    days_to_long_term=days_to_lt,
                    basis_unknown=buy_trade.basis_unknown,
                    is_option=False,
                )
            )

    return AllocationResult(realized_pairs=all_realized, open_lots=all_open)


def compute_tax_position(trades: list[Trade], year: int) -> TaxPosition:
    """Aggregate YTD realized gains/losses with ST/LT classification.

    Option trades are included. basis_unknown pairs are excluded and counted.
    Only sells in the given year contribute.
    """
    result = _allocate_lots(trades, as_of=date(year, 12, 31))

    st_gains = 0.0
    st_losses = 0.0
    lt_gains = 0.0
    lt_losses = 0.0
    basis_unknown_count = 0

    # Build sell trade lookup for year filtering
    sell_map = {t.id: t for t in trades if t.is_sell()}

    for rp in result.realized_pairs:
        sell_trade = sell_map.get(rp.sell_trade_id)
        if sell_trade is None or sell_trade.date.year != year:
            continue

        if rp.basis_unknown:
            basis_unknown_count += 1
            continue

        gain_loss = rp.proceeds - rp.basis

        if rp.is_long_term:
            if gain_loss >= 0:
                lt_gains += gain_loss
            else:
                lt_losses += abs(gain_loss)
        else:
            if gain_loss >= 0:
                st_gains += gain_loss
            else:
                st_losses += abs(gain_loss)

    return TaxPosition(
        st_gains=round(st_gains, 2),
        st_losses=round(st_losses, 2),
        lt_gains=round(lt_gains, 2),
        lt_losses=round(lt_losses, 2),
        year=year,
        basis_unknown_count=basis_unknown_count,
    )


def identify_open_lots(trades: list[Trade], as_of: date) -> list[OpenLot]:
    """Return remaining open lots sorted by days_to_long_term ascending, then ticker.

    Options are excluded. Already-long-term lots sort to the end.
    """
    result = _allocate_lots(trades, as_of=as_of)

    # Sort: lots still approaching LT threshold first (ascending), then already-LT lots.
    # Within same days_to_long_term, sort by ticker alphabetically.
    def sort_key(lot: OpenLot) -> tuple[int, int, str]:
        # already LT (days_to_long_term == 0) sorts after all others
        is_already_lt = 1 if lot.days_to_long_term == 0 else 0
        return (is_already_lt, lot.days_to_long_term, lot.ticker)

    return sorted(result.open_lots, key=sort_key)


def select_lots(
    open_lots: list[OpenLot],
    ticker: str,
    qty: float,
    method: str,
    price: float,
) -> LotSelection | None:
    """Apply FIFO/HIFO/LIFO to select lots for a simulated sell.

    Pools across accounts. Returns None if insufficient shares available.
    wash_sale_risk is always False — caller sets it based on look-back triggers.
    """
    ticker_lots = [lot for lot in open_lots if lot.ticker == ticker]

    total_available = sum(lot.quantity for lot in ticker_lots)
    if total_available < qty:
        return None

    # Sort by method
    if method == "FIFO":
        sorted_lots = sorted(ticker_lots, key=lambda lot: (lot.purchase_date, lot.account))
    elif method == "HIFO":
        sorted_lots = sorted(ticker_lots, key=lambda lot: -lot.adjusted_basis_per_share)
    elif method == "LIFO":
        sorted_lots = sorted(ticker_lots, key=lambda lot: lot.purchase_date, reverse=True)
    else:
        return None

    lots_used: list[OpenLot] = []
    st_gain_loss = 0.0
    lt_gain_loss = 0.0
    remaining = qty

    for lot in sorted_lots:
        if remaining <= 0:
            break

        consumed = min(remaining, lot.quantity)
        gain_loss = round((price - lot.adjusted_basis_per_share) * consumed, 2)

        is_lt = lot.days_to_long_term == 0

        # Create a copy of the lot reflecting consumed quantity
        used_lot = lot.model_copy(update={"quantity": consumed})
        lots_used.append(used_lot)

        if is_lt:
            lt_gain_loss += gain_loss
        else:
            st_gain_loss += gain_loss

        remaining -= consumed

    return LotSelection(
        method=method,
        lots_used=lots_used,
        st_gain_loss=round(st_gain_loss, 2),
        lt_gain_loss=round(lt_gain_loss, 2),
        total_gain_loss=round(st_gain_loss + lt_gain_loss, 2),
        wash_sale_risk=False,
    )


def recommend_lot_method(
    selections: dict[str, LotSelection],
    tax_position: TaxPosition,
    safe_sell_date: date | None = None,
) -> LotRecommendation:
    """Rule-based decision tree for lot method recommendation.

    Priority:
    1. ST loss offset (if user has net ST gains)
    2. If preferred has wash risk → flag, suggest wait, find fallback
    3. Prefer LT gain over ST gain (lower tax rate)
    4. Prefer smaller total gain
    5. Tiebreak: FIFO
    """
    has_st_gains = tax_position.net_st > 0

    # Separate into loss-producers and gain-producers
    st_loss_methods = {m: s for m, s in selections.items() if s.st_gain_loss < 0 or s.lt_gain_loss < 0}

    # Rule 1: prefer ST loss offset if user has ST gains
    if has_st_gains and st_loss_methods:
        # Pick the method with the largest ST loss (most offset)
        best_loss_method = min(
            st_loss_methods.keys(),
            key=lambda m: st_loss_methods[m].total_gain_loss,
        )
        best = st_loss_methods[best_loss_method]

        if best.wash_sale_risk:
            # Find fallback: best clean option
            fallback = _find_fallback(selections, st_loss_methods)
            return LotRecommendation(
                preferred_method=best_loss_method,
                reason="st_loss_offset",
                has_wash_risk=True,
                safe_sell_date=safe_sell_date,
                fallback_method=fallback[0] if fallback else None,
                fallback_reason=fallback[1] if fallback else None,
            )
        else:
            return LotRecommendation(
                preferred_method=best_loss_method,
                reason="st_loss_offset",
                has_wash_risk=False,
                safe_sell_date=None,
                fallback_method=None,
                fallback_reason=None,
            )

    # Rule 2: no losses available — prefer LT gain over ST gain
    lt_only = {
        m: s for m, s in selections.items() if s.lt_gain_loss > 0 and s.st_gain_loss <= 0 and not s.wash_sale_risk
    }
    if lt_only:
        st_methods = {m: s for m, s in selections.items() if s.st_gain_loss > 0}
        if st_methods:
            best_lt = min(lt_only.keys(), key=lambda m: lt_only[m].total_gain_loss)
            return LotRecommendation(
                preferred_method=best_lt,
                reason="lt_lower_rate",
                has_wash_risk=False,
                safe_sell_date=None,
                fallback_method=None,
                fallback_reason=None,
            )

    # Rule 3: prefer smallest total gain
    clean_methods = {m: s for m, s in selections.items() if not s.wash_sale_risk}
    if clean_methods:
        best = min(clean_methods.keys(), key=lambda m: (clean_methods[m].total_gain_loss, m != "FIFO"))
        return LotRecommendation(
            preferred_method=best,
            reason="least_gain",
            has_wash_risk=False,
            safe_sell_date=None,
            fallback_method=None,
            fallback_reason=None,
        )

    # Rule 4: all have wash risk
    best = min(selections.keys(), key=lambda m: selections[m].total_gain_loss)
    return LotRecommendation(
        preferred_method=best,
        reason="st_loss_offset" if selections[best].total_gain_loss < 0 else "least_gain",
        has_wash_risk=True,
        safe_sell_date=safe_sell_date,
        fallback_method=None,
        fallback_reason=None,
    )


def _find_fallback(
    all_selections: dict[str, LotSelection],
    exclude: dict[str, LotSelection],
) -> tuple[str, str] | None:
    """Find the best clean (no wash risk) fallback method."""
    clean = {m: s for m, s in all_selections.items() if m not in exclude and not s.wash_sale_risk}
    if not clean:
        # Check if any of the excluded methods have clean alternatives
        clean = {m: s for m, s in all_selections.items() if not s.wash_sale_risk}
    if not clean:
        return None

    # Prefer LT gain, then smallest gain, tiebreak FIFO
    lt_clean = {m: s for m, s in clean.items() if s.lt_gain_loss > 0 and s.st_gain_loss <= 0}
    if lt_clean:
        best = min(lt_clean.keys(), key=lambda m: lt_clean[m].total_gain_loss)
        return (best, "lt_lower_rate")

    best = min(clean.keys(), key=lambda m: clean[m].total_gain_loss)
    return (best, "least_gain")
