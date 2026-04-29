"""Pure function that ranks open positions by unrealized $ change.

Used by the Overview page Top Movers panel. Caller passes in PositionRow
instances (already computed by portfolio/positions.py); this module sorts
and slices, no DB or quote access.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from net_alpha.portfolio.models import PositionRow


@dataclass(frozen=True)
class MoverRow:
    symbol: str
    unrealized_dollar: Decimal
    unrealized_pct: Decimal | None  # None when open_cost == 0
    market_value: Decimal


@dataclass(frozen=True)
class TopMoversView:
    winners: list[MoverRow]
    losers: list[MoverRow]


def _to_mover(r: PositionRow) -> MoverRow:
    pct: Decimal | None
    if r.open_cost and r.open_cost != Decimal("0") and r.unrealized_pl is not None:
        pct = (r.unrealized_pl / r.open_cost * Decimal("100")).quantize(Decimal("0.1"))
    else:
        pct = None
    return MoverRow(
        symbol=r.symbol,
        unrealized_dollar=r.unrealized_pl or Decimal("0"),
        unrealized_pct=pct,
        market_value=r.market_value or Decimal("0"),
    )


def build_top_movers(positions: list[PositionRow], k: int = 3) -> TopMoversView:
    """Return top-k winners and losers by unrealized $ change.

    Excludes positions with no market value (no live quote). Ties broken by
    symbol ascending so output is deterministic.
    """
    priced = [p for p in positions if p.market_value is not None and p.unrealized_pl is not None]
    pos = sorted(
        [p for p in priced if p.unrealized_pl > 0],
        key=lambda p: (-p.unrealized_pl, p.symbol),
    )
    neg = sorted(
        [p for p in priced if p.unrealized_pl < 0],
        key=lambda p: (p.unrealized_pl, p.symbol),
    )
    return TopMoversView(
        winners=[_to_mover(p) for p in pos[:k]],
        losers=[_to_mover(p) for p in neg[:k]],
    )
