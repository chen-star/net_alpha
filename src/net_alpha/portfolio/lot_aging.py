"""Top open lots about to cross the long-term capital gains threshold.

LTCG threshold = acquired_on + 365 days. Returns lots whose days_to_ltcg is
in [1, horizon_days], sorted by urgency (smallest days_to_ltcg first).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from decimal import Decimal

from net_alpha.models.domain import Lot
from net_alpha.portfolio.models import AgingLot


def top_lots_crossing_ltcg(*, lots: Iterable[Lot], horizon_days: int = 90, top_n: int = 5) -> list[AgingLot]:
    today = dt.date.today()
    candidates: list[AgingLot] = []
    for lot in lots:
        if lot.option_details is not None or lot.quantity <= 0:
            continue
        ltcg_date = lot.date + dt.timedelta(days=365)
        days = (ltcg_date - today).days
        if days < 1 or days > horizon_days:
            continue
        candidates.append(
            AgingLot(
                symbol=lot.ticker,
                account=lot.account,
                qty=Decimal(str(lot.quantity)),
                acquired_on=lot.date,
                days_to_ltcg=days,
            )
        )
    candidates.sort(key=lambda a: a.days_to_ltcg)
    return candidates[:top_n]
