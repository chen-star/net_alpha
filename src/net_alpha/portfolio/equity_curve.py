"""Year-scoped cumulative realized P&L line + present-day unrealized dot.

The chart renders two parallel series so the user can read both numbers off the
same axis:
  • realized cumulative — steps up at each sell event
  • total = realized + present unrealized — same shape, offset upward by today's
    unrealized; the gap between the two lines IS the unrealized component

Phase 1 limitation: backfill of historical unrealized requires end-of-day price
snapshots, which we don't yet persist. We approximate the total line by adding
*today's* unrealized to every point; the line shifts in parallel rather than
reflecting how unrealized actually moved over the year.
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

    def _make(on: dt.date, cum: Decimal, unrealized: Decimal | None) -> EquityPoint:
        total = cum + present_unrealized if present_unrealized is not None else None
        return EquityPoint(on=on, cumulative_realized=cum, unrealized=unrealized, total_pl=total)

    points: list[EquityPoint] = [_make(dt.date(year, 1, 1), Decimal("0"), None)]
    cum = Decimal("0")
    for t in sells:
        cum += Decimal(str((t.proceeds or 0) - (t.cost_basis or 0)))
        points.append(_make(t.date, cum, None))

    today = dt.date.today()
    last_day = today if today.year == year else dt.date(year, 12, 31)
    if points[-1].on != last_day:
        # Only append a trailing point when there is something meaningful to show:
        # either we have unrealized data, or we have at least one sell point to
        # "close" the line at the year boundary / today.
        if present_unrealized is not None or sells:
            points.append(_make(last_day, cum, present_unrealized))
    elif present_unrealized is not None:
        points[-1] = _make(last_day, cum, present_unrealized)
    return points
