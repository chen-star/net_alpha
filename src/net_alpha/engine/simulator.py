# src/net_alpha/engine/simulator.py
from __future__ import annotations

from datetime import date as _date
from datetime import timedelta
from decimal import Decimal

from net_alpha.engine.matcher import get_match_confidence, is_within_wash_sale_window
from net_alpha.models.domain import (
    Account,
    LotConsumption,
    SimBuyMatch,
    SimulationBuyOption,
    SimulationOption,
    Trade,
    WashSaleViolation,
)


def simulate_sell(
    ticker: str,
    qty: Decimal,
    price: Decimal,
    accounts: list[Account],
    existing_lots,  # list[Lot]
    recent_trades: list[Trade],
    today: _date | None = None,
) -> list[SimulationOption]:
    """One option per account that holds the ticker. Cross-account wash-sale check."""
    today = today or _date.today()
    qty_f = float(qty)
    price_f = float(price)

    options: list[SimulationOption] = []
    for account in accounts:
        held = sorted(
            [lot for lot in existing_lots if lot.account == account.display() and lot.ticker == ticker],
            key=lambda lot: lot.date,
        )
        available = sum(lot.quantity for lot in held)
        if available <= 0:
            continue

        # FIFO consumption — up to qty_f or available
        target = min(qty_f, available)
        consumed: list[LotConsumption] = []
        realized = 0.0
        remaining = target
        for lot in held:
            if remaining <= 0:
                break
            take = min(remaining, lot.quantity)
            basis_per_share = (lot.adjusted_basis / lot.quantity) if lot.quantity else 0.0
            realized += take * (price_f - basis_per_share)
            consumed.append(
                LotConsumption(
                    lot_id=int(lot.id) if lot.id and lot.id.isdigit() else 0,
                    quantity=Decimal(str(take)),
                    basis_per_share=Decimal(str(round(basis_per_share, 4))),
                    purchase_date=lot.date,
                )
            )
            remaining -= take

        is_loss = realized < 0
        would_trigger = False
        confidence = "N/A"
        blocking: list[Trade] = []
        lookforward = None

        if is_loss:
            consumed_basis_total = sum(float(c.quantity) * float(c.basis_per_share) for c in consumed)
            hypo_sell = Trade(
                account=account.display(),
                date=today,
                ticker=ticker,
                action="Sell",
                quantity=target,
                proceeds=target * price_f,
                cost_basis=consumed_basis_total,
            )
            for t in recent_trades:
                if t.id == hypo_sell.id:
                    continue
                if not is_within_wash_sale_window(today, t.date):
                    continue
                conf = get_match_confidence(hypo_sell, t, etf_pairs={})
                if conf is not None:
                    blocking.append(t)
                    if confidence == "N/A" or conf == "Confirmed":
                        confidence = conf
                    would_trigger = True
            lookforward = today + timedelta(days=30)

        options.append(
            SimulationOption(
                account=account,
                lots_consumed_fifo=consumed,
                realized_pnl=Decimal(str(round(realized, 2))),
                would_trigger_wash_sale=would_trigger,
                blocking_buys=blocking,
                lookforward_block_until=lookforward,
                confidence=confidence,
                insufficient_shares=qty_f > available,
                available_shares=Decimal(str(available)),
            )
        )

    return options


def simulate_buy(
    ticker: str,
    qty: Decimal,
    price: Decimal,
    account: str | None,
    on_date: _date,
    accounts: list[Account],
    recent_trades: list[Trade],
    existing_violations: list[WashSaleViolation],
    etf_pairs: dict[str, list[str]],
) -> list[SimulationBuyOption]:
    """One option per candidate buy account. Cross-account loss scan."""
    candidate_accounts = accounts if account is None else [a for a in accounts if a.display() == account]
    matched_loss_ids = {v.loss_trade_id for v in existing_violations}

    # Hypothetical buy used as the right-hand side of get_match_confidence(loss, hypo_buy).
    # get_match_confidence works off ticker / action / option_details, so the float-coerced
    # numerics here are inert; precision math runs in Decimal below.
    hypo_buy_template = Trade(
        account="",  # filled per-option
        date=on_date,
        ticker=ticker,
        action="Buy",
        quantity=float(qty),
        proceeds=None,
        cost_basis=float(qty * price),
    )

    # Pre-filter recent_trades to candidate loss sales in the look-back window.
    eligible_losses: list[Trade] = []
    for t in recent_trades:
        if not t.is_sell() or not t.is_loss():
            continue
        if t.id in matched_loss_ids:
            continue
        delta = (on_date - t.date).days
        if not (0 <= delta <= 30):
            continue
        eligible_losses.append(t)

    # Stable order: oldest loss first (FIFO consumption of the proposed buy quantity).
    eligible_losses.sort(key=lambda x: (x.date, x.id))

    options: list[SimulationBuyOption] = []
    proposed_basis = (qty * price).quantize(Decimal("0.01"))

    for acct in candidate_accounts:
        hypo_buy = hypo_buy_template.model_copy(update={"account": acct.display()})
        matches: list[SimBuyMatch] = []
        remaining = qty
        total_disallowed = Decimal("0")

        for loss in eligible_losses:
            if remaining <= 0:
                break
            confidence = get_match_confidence(loss, hypo_buy, etf_pairs)
            if confidence is None:
                continue
            loss_qty = Decimal(str(loss.quantity))
            if loss_qty <= 0:
                continue
            matched_qty = min(remaining, loss_qty)
            loss_amount = Decimal(str(loss.loss_amount()))
            disallowed_dec = (loss_amount * matched_qty / loss_qty).quantize(Decimal("0.01"))
            total_disallowed += disallowed_dec
            matches.append(
                SimBuyMatch(
                    loss_trade_id=loss.id,
                    loss_sale_date=loss.date,
                    loss_account=loss.account,
                    loss_ticker=loss.ticker,
                    matched_quantity=matched_qty,
                    disallowed_loss=disallowed_dec,
                    confidence=confidence,
                )
            )
            remaining -= matched_qty

        options.append(
            SimulationBuyOption(
                account=acct,
                matches=matches,
                total_disallowed=total_disallowed,
                proposed_basis=proposed_basis,
                adjusted_basis=proposed_basis + total_disallowed,
                clean=(not matches),
            )
        )

    return options
