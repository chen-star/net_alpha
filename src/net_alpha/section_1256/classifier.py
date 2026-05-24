"""§1256 closed-trade classifier — 60/40 LT/ST split per IRC §1256(a)(3)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import date as _date
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

    Audit #35: ``prior_year_mtm_basis_fn`` returns a per-contract FMV for the
    position. The previous implementation applied it to the FULL sell qty
    indiscriminately, which mis-priced sells that mixed prior-year-marked
    contracts with new opens added after year-end. The fix derives the
    MTM-marked qty per position (from open_section_1256_positions evaluated
    at last_business_day of the prior tax year) and consumes that qty FIFO
    across subsequent sells. Once marked qty is exhausted, basis falls back
    to actual lot basis for the remainder.
    """
    from net_alpha.pricing.year_end import last_business_day as _lbd
    from net_alpha.section_1256.mtm import open_section_1256_positions
    from net_alpha.section_1256.mtm import position_key as _pkey
    from net_alpha.section_1256.universe import load_universe

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

    # Audit #35: per-position marked-qty tracking. open_section_1256_positions
    # tells us the EOY-marked qty for each long position; subsequent sells
    # consume marked qty FIFO at prior_fmv per contract. Marked qty is
    # logically backed by lots dated on/before the prior year-end; fresh
    # opens are lots dated after.
    universe = load_universe()
    years_needed: set[int] = {sell.date.year - 1 for sell in sorted_sells}
    # (position_key, year) -> remaining marked qty (consumed FIFO across sells).
    marked_qty_remaining: dict[tuple[str, int], Decimal] = {}
    # (position_key, year) -> last_business_day of `year`, for fresh-lot filter.
    prior_lbd: dict[tuple[str, int], _date] = {}
    if prior_year_mtm_basis_fn is not None and years_needed:
        for year in years_needed:
            as_of = _lbd(year)
            try:
                positions = open_section_1256_positions(trades, lots, universe, as_of=as_of)
            except Exception:
                positions = []
            for pos in positions:
                if pos.option_details is None or pos.quantity <= 0:
                    # Shorts (qty < 0) are not closed by Sell trades, so they
                    # don't appear in the classifier's FIFO loop; skip.
                    continue
                pk = _pkey(account=pos.account, ticker=pos.ticker, option_details=pos.option_details)
                marked_qty_remaining[(pk, year)] = Decimal(str(pos.quantity))
                prior_lbd[(pk, year)] = as_of

    out: list[Section1256Classification] = []
    for sell in sorted_sells:
        if sell.option_details is None:
            # Defensive: §1256 trades that aren't option contracts skip this
            # path; basis is then zero (legacy behavior).
            basis = Decimal("0")
            out.append(
                Section1256Classification(
                    trade_id=sell.id,
                    realized_pnl=Decimal(str(sell.proceeds)) - basis if sell.proceeds is not None else -basis,
                    long_term_portion=Decimal("0"),
                    short_term_portion=Decimal("0"),
                    underlying=sell.ticker,
                )
            )
            continue

        k = (sell.account, sell.ticker, _opt_key(sell.option_details))
        chain = lots_by_key.get(k, [])
        sell_qty = Decimal(str(sell.quantity))

        pk = _pkey(account=sell.account, ticker=sell.ticker, option_details=sell.option_details)
        prior_year = sell.date.year - 1
        prior_fmv: Decimal | None = None
        if prior_year_mtm_basis_fn is not None:
            prior_fmv = prior_year_mtm_basis_fn(pk, prior_year)

        marked_used = Decimal("0")
        marked_basis = Decimal("0")
        if prior_fmv is not None:
            mq_key = (pk, prior_year)
            marked_remaining = marked_qty_remaining.get(mq_key)
            if marked_remaining is None:
                # Backwards-compat: no marked-qty info (legacy callers /
                # tests that don't seed lots for open_section_1256_positions
                # to find). Apply prior_fmv to the full sell qty.
                marked_used = sell_qty
                marked_basis = sell_qty * prior_fmv
            elif marked_remaining > 0:
                marked_used = min(sell_qty, marked_remaining)
                marked_basis = marked_used * prior_fmv
                marked_qty_remaining[mq_key] = marked_remaining - marked_used

        # The marked portion is logically backed by pre-EOY lots; consume
        # them from the FIFO chain by quantity (not by basis) so they're
        # removed from later sells' fresh-lot pool. The basis of those
        # consumed pre-EOY lots is intentionally discarded — prior_fmv
        # supersedes original basis after §1256(a)(2) MTM.
        marked_to_drain = marked_used
        pre_eoy_cutoff = prior_lbd.get((pk, prior_year)) if prior_fmv is not None else None
        for lot in chain:
            if marked_to_drain <= 0:
                break
            if pre_eoy_cutoff is not None and lot.date > pre_eoy_cutoff:
                continue
            avail = remaining_per_lot.get(lot.id, Decimal("0"))
            if avail <= 0:
                continue
            take = min(marked_to_drain, avail)
            remaining_per_lot[lot.id] = avail - take
            marked_to_drain -= take

        # The fresh portion (sell qty beyond what marked covered) draws
        # basis from remaining FIFO lots — typically post-EOY opens after
        # pre-EOY inventory was consumed above.
        fresh_qty = sell_qty - marked_used
        fresh_basis = Decimal("0")
        for lot in chain:
            if fresh_qty <= 0:
                break
            avail = remaining_per_lot.get(lot.id, Decimal("0"))
            if avail <= 0:
                continue
            take = min(fresh_qty, avail)
            original_qty = Decimal(str(lot.quantity))
            per_unit = Decimal(str(lot.adjusted_basis)) / original_qty if original_qty > 0 else Decimal("0")
            fresh_basis += take * per_unit
            remaining_per_lot[lot.id] = avail - take
            fresh_qty -= take

        basis = marked_basis + fresh_basis

        proceeds = Decimal(str(sell.proceeds)) if sell.proceeds is not None else Decimal("0")
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
