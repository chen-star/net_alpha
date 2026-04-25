# src/net_alpha/engine/simulator.py
from __future__ import annotations

from datetime import date as _date
from datetime import timedelta
from decimal import Decimal

from net_alpha.engine.matcher import get_match_confidence, is_within_wash_sale_window
from net_alpha.models.domain import (
    Account,
    LotConsumption,
    SimulationOption,
    Trade,
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
