"""§1256 closed-trade classifier — 60/40 LT/ST split per IRC §1256(a)(3)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from decimal import Decimal

from net_alpha.models.domain import Lot, Section1256Classification, Trade

_LT_FRACTION = Decimal("0.60")
_ST_FRACTION = Decimal("0.40")


def classify_closed_trades(
    trades: list[Trade],
    lots: list[Lot],
    *,
    prior_year_mtm_basis_fn: Callable[[str, int], Decimal | None] | None = None,
) -> list[Section1256Classification]:
    """Compute 60/40 LT/ST split per §1256(a)(3); use prior-year MTM basis per §1256(a)(2) when supplied.

    Walks sells in date order while maintaining shared per-(ticker, option,
    account) FIFO consumption state, so sequential sells of the same contract
    over the year don't all read basis from the oldest (already-consumed) lot.
    """
    from net_alpha.section_1256.mtm import position_key as _pkey

    # Pre-bucket lots per (account, ticker, option-contract-id) and remember
    # the remaining-consumable quantity per lot. FIFO ordering is by lot.date.
    # OptionDetails is a non-hashable Pydantic model, so we key on a tuple of
    # its identifying fields.
    def _opt_key(opt) -> tuple:
        return (opt.strike, opt.expiry.isoformat(), opt.call_put)

    lots_by_key: dict[tuple, list[Lot]] = defaultdict(list)
    for lot in lots:
        if lot.option_details is None:
            continue
        k = (lot.account, lot.ticker, _opt_key(lot.option_details))
        lots_by_key[k].append(lot)
    for k, ls in lots_by_key.items():
        ls.sort(key=lambda lot: lot.date)

    remaining_per_lot: dict[str, Decimal] = {
        lot.id: Decimal(str(lot.quantity)) for ls in lots_by_key.values() for lot in ls
    }

    # Sells in date order so FIFO consumption is correct across multiple
    # same-year sells of the same contract key.
    sorted_sells = sorted(
        (t for t in trades if t.is_section_1256 and t.is_sell()),
        key=lambda t: t.date,
    )

    out: list[Section1256Classification] = []
    for sell in sorted_sells:
        if sell.option_details is None:
            # Defensive: §1256 trades that aren't option contracts skip this
            # path; basis is then zero (legacy behavior).
            basis = Decimal("0")
        else:
            k = (sell.account, sell.ticker, _opt_key(sell.option_details))
            chain = lots_by_key.get(k, [])
            remaining = Decimal(str(sell.quantity))
            basis = Decimal("0")
            for lot in chain:
                if remaining <= 0:
                    break
                avail = remaining_per_lot.get(lot.id, Decimal("0"))
                if avail <= 0:
                    continue
                take = min(remaining, avail)
                original_qty = Decimal(str(lot.quantity))
                per_unit = (
                    Decimal(str(lot.adjusted_basis)) / original_qty if original_qty > 0 else Decimal("0")
                )
                basis += take * per_unit
                remaining_per_lot[lot.id] = avail - take
                remaining -= take

        if prior_year_mtm_basis_fn is not None and sell.option_details is not None:
            pk = _pkey(account=sell.account, ticker=sell.ticker, option_details=sell.option_details)
            prior_fmv = prior_year_mtm_basis_fn(pk, sell.date.year - 1)
            if prior_fmv is not None:
                # `prior_fmv` is per-contract. Per §1256(a)(2), the basis for
                # the sell is qty × prior-year-end FMV. Using bare `prior_fmv`
                # was correct only for qty=1 and incorrect for every other
                # quantity (basis = $F instead of qty×$F).
                basis = Decimal(str(sell.quantity)) * prior_fmv

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
