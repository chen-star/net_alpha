"""Year-scoped cumulative realized P&L line + present-day unrealized dot.

Phase 1 limitation: backfill of historical unrealized requires end-of-day price
snapshots, which we don't yet persist. The line is realized-only across the
year; only the present-day point carries `unrealized`.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from decimal import Decimal

from net_alpha.models.domain import Trade
from net_alpha.portfolio.models import EquityPoint


def build_equity_curve(
    *,
    trades: Iterable[Trade],
    year: int,
    present_unrealized: Decimal | None,
) -> list[EquityPoint]:
    sells = sorted(
        (t for t in trades if t.action.lower() == "sell" and t.date.year == year),
        key=lambda t: t.date,
    )

    points: list[EquityPoint] = [EquityPoint(on=dt.date(year, 1, 1), cumulative_realized=Decimal("0"), unrealized=None)]
    cum = Decimal("0")
    for t in sells:
        cum += Decimal(str((t.proceeds or 0) - (t.cost_basis or 0)))
        points.append(EquityPoint(on=t.date, cumulative_realized=cum, unrealized=None))

    today = dt.date.today()
    last_day = today if today.year == year else dt.date(year, 12, 31)
    if points[-1].on != last_day:
        # Only append a trailing point when there is something meaningful to show:
        # either we have unrealized data, or we have at least one sell point to
        # "close" the line at the year boundary / today.
        if present_unrealized is not None or sells:
            points.append(EquityPoint(on=last_day, cumulative_realized=cum, unrealized=present_unrealized))
    elif present_unrealized is not None:
        points[-1] = EquityPoint(on=last_day, cumulative_realized=cum, unrealized=present_unrealized)
    return points
