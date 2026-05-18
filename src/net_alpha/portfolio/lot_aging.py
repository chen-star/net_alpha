"""Top open lots about to cross the long-term capital gains threshold.

LTCG threshold = acquired_on + 365 days. Returns lots whose days_to_ltcg is
in [1, horizon_days], sorted by urgency (smallest days_to_ltcg first).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from decimal import Decimal

from net_alpha.models.domain import Lot, Trade
from net_alpha.portfolio.models import AgingLot
from net_alpha.portfolio.positions import consume_lots_fifo


def top_lots_crossing_ltcg(
    *,
    lots: Iterable[Lot],
    trades: Iterable[Trade] | None = None,
    gl_closures: dict | None = None,
    gl_option_closures: dict | None = None,
    horizon_days: int = 90,
    top_n: int = 5,
) -> list[AgingLot]:
    """Return open equity lots that will cross the LTCG line within
    ``horizon_days`` days.

    When ``trades`` is supplied, FIFO consumption is applied so lots that
    have already been fully closed by later sells don't surface here —
    ``lot.quantity`` is the *original* buy size and is never decremented
    on the row itself. Callers that don't yet pass trades fall back to
    the legacy "iterate raw lots" behavior; that path mis-classifies a
    fully-sold lot as open and is preserved only for back-compat with
    older test fixtures.
    """
    today = dt.date.today()

    # Resolve remaining qty per lot. Lots get keyed by (lot.id) to avoid
    # collisions on duplicate ticker/account combinations.
    if trades is not None:
        consumed = consume_lots_fifo(
            lots=list(lots),
            trades=list(trades),
            gl_closures=gl_closures or {},
            gl_option_closures=gl_option_closures or {},
        )
        iter_with_qty = ((lot, float(remaining_qty)) for lot, remaining_qty, _basis in consumed)
    else:
        iter_with_qty = ((lot, float(lot.quantity)) for lot in lots)

    candidates: list[AgingLot] = []
    for lot, remaining_qty in iter_with_qty:
        if lot.option_details is not None or remaining_qty <= 0:
            continue
        # IRC §1223(4): the LTCG clock starts at the effective acquired date.
        ltcg_date = lot.effective_acquired_date() + dt.timedelta(days=365)
        days = (ltcg_date - today).days
        if days < 1 or days > horizon_days:
            continue
        candidates.append(
            AgingLot(
                symbol=lot.ticker,
                account=lot.account,
                qty=Decimal(str(remaining_qty)),
                acquired_on=lot.date,
                days_to_ltcg=days,
            )
        )
    candidates.sort(key=lambda a: a.days_to_ltcg)
    return candidates[:top_n]
