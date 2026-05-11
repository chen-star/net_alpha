"""§1256 closed-trade classifier — 60/40 LT/ST split per IRC §1256(a)(3)."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from net_alpha.models.domain import Lot, Section1256Classification, Trade

_LT_FRACTION = Decimal("0.60")
_ST_FRACTION = Decimal("0.40")


def _matched_basis_fifo(sell: Trade, lots: list[Lot]) -> Decimal:
    """FIFO-matched lot basis for `sell` (legacy path)."""
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
    *,
    prior_year_mtm_basis_fn: Callable[[str, int], Decimal | None] | None = None,
) -> list[Section1256Classification]:
    """Compute 60/40 LT/ST split per §1256(a)(3); use prior-year MTM basis per §1256(a)(2) when supplied."""
    from net_alpha.section_1256.mtm import position_key as _pkey

    out: list[Section1256Classification] = []
    for sell in trades:
        if not sell.is_section_1256:
            continue
        if not sell.is_sell():
            continue
        basis = _matched_basis_fifo(sell, lots)

        if prior_year_mtm_basis_fn is not None and sell.option_details is not None:
            pk = _pkey(account=sell.account, ticker=sell.ticker, option_details=sell.option_details)
            prior_fmv = prior_year_mtm_basis_fn(pk, sell.date.year - 1)
            if prior_fmv is not None:
                basis = prior_fmv

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
