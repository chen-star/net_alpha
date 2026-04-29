"""§1256 closed-trade classifier — 60/40 LT/ST split per IRC §1256(a)(3).

Pure function. Runs after the detector during recompute. Reads from existing
Lot records (FIFO basis) and the Trade list. Open positions are NOT classified
in v1 — Dec 31 mark-to-market is out of scope (see spec Q2/B).
"""

from __future__ import annotations

from decimal import Decimal

from net_alpha.models.domain import Lot, Section1256Classification, Trade

_LT_FRACTION = Decimal("0.60")
_ST_FRACTION = Decimal("0.40")


def _matched_basis_fifo(sell: Trade, lots: list[Lot]) -> Decimal:
    """Return the cost basis of the lot(s) matched FIFO to *sell*.

    Matches by ticker + option-details (strike/expiry/call_put) for options,
    or by ticker for stocks. Quantity-weighted. Idempotent on its inputs.

    Note: Lot.date is the acquisition date field (domain model uses `date`,
    not `acquired_date`).
    """
    remaining = Decimal(str(sell.quantity))
    basis = Decimal("0")
    matching = sorted(
        [lot for lot in lots if lot.ticker == sell.ticker and lot.option_details == sell.option_details],
        key=lambda lot: lot.date,
    )
    for lot in matching:
        if remaining <= 0:
            break
        take = min(remaining, Decimal(str(lot.quantity)))
        per_unit = Decimal(str(lot.adjusted_basis)) / Decimal(str(lot.quantity))
        basis += take * per_unit
        remaining -= take
    return basis


def classify_closed_trades(
    trades: list[Trade],
    lots: list[Lot],
) -> list[Section1256Classification]:
    """For each closed §1256 trade, compute realized P&L and split 60/40."""
    out: list[Section1256Classification] = []
    for sell in trades:
        if not sell.is_section_1256:
            continue
        if not sell.is_sell():
            continue
        # If sell qty exceeds matched lot qty, basis is partial; v1 accepts under-attribution.
        basis = _matched_basis_fifo(sell, lots)
        proceeds = Decimal(str(sell.proceeds))
        realized = proceeds - basis
        out.append(
            Section1256Classification(
                trade_id=sell.id,
                realized_pnl=realized,
                long_term_portion=realized * _LT_FRACTION,
                short_term_portion=realized * _ST_FRACTION,
                underlying=sell.ticker,
            )
        )
    return out
