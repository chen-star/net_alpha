"""Pure function that ranks open positions by *lifetime* unrealized P&L.

Used by the Overview page panel historically labeled "Top Movers". Despite
that label, the ranking is over **lifetime** unrealized P&L since each
position was opened — NOT a session / 1-day mark-to-market window. The
panel is more honestly described as "Largest unrealized gains/losses";
the ``build_largest_unrealized`` / ``LargestUnrealizedView`` /
``gains`` / ``losses`` names below are the primary surface, with the
``build_top_movers`` / ``TopMoversView`` / ``winners`` / ``losers`` names
kept as back-compat aliases for callers (the web route + template) that
haven't switched yet.

Caller passes in PositionRow instances (already computed by
portfolio/positions.py); this module sorts and slices, no DB or quote
access.

TODO(audit #6): once the web route + template move to the clarified
names, drop the back-compat aliases.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from net_alpha.portfolio.models import PositionRow


@dataclass(frozen=True)
class MoverRow:
    """One ranked position. ``unrealized_dollar`` is lifetime unrealized
    P&L since acquisition — not a 1-day delta."""

    symbol: str
    unrealized_dollar: Decimal
    unrealized_pct: Decimal | None  # None when open_cost == 0
    market_value: Decimal


@dataclass(frozen=True, init=False)
class LargestUnrealizedView:
    """Top-k positions by lifetime unrealized gain and loss.

    ``gains`` and ``losses`` are the clarified field names. ``winners`` /
    ``losers`` are back-compat property aliases pointing at the same
    lists; new code should reach for ``gains`` / ``losses``.

    The custom ``__init__`` accepts BOTH the new (``gains`` / ``losses``)
    and legacy (``winners`` / ``losers``) kwargs so callers and fixtures
    written against the old API keep working until the back-compat
    aliases are removed (TODO audit #6).
    """

    gains: list[MoverRow]
    losses: list[MoverRow]

    def __init__(
        self,
        gains: list[MoverRow] | None = None,
        losses: list[MoverRow] | None = None,
        *,
        winners: list[MoverRow] | None = None,
        losers: list[MoverRow] | None = None,
    ) -> None:
        resolved_gains = gains if gains is not None else (winners if winners is not None else [])
        resolved_losses = losses if losses is not None else (losers if losers is not None else [])
        # Frozen dataclass: bypass the __setattr__ guard.
        object.__setattr__(self, "gains", resolved_gains)
        object.__setattr__(self, "losses", resolved_losses)

    @property
    def winners(self) -> list[MoverRow]:
        # TODO(audit #6): drop once web route/template migrate to ``gains``.
        return self.gains

    @property
    def losers(self) -> list[MoverRow]:
        # TODO(audit #6): drop once web route/template migrate to ``losses``.
        return self.losses


# Back-compat alias for callers importing the legacy name.
# TODO(audit #6): drop once web route migrates to ``LargestUnrealizedView``.
TopMoversView = LargestUnrealizedView


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


def build_largest_unrealized(positions: list[PositionRow], k: int = 3) -> LargestUnrealizedView:
    """Return the top-k positions by *lifetime* unrealized gain and loss.

    The ranking is by lifetime unrealized P&L since each position was
    opened — NOT a session / 1-day mark-to-market delta. Positions with
    no market value (no live quote) are excluded. Ties broken by symbol
    ascending so output is deterministic.
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
    return LargestUnrealizedView(
        gains=[_to_mover(p) for p in pos[:k]],
        losses=[_to_mover(p) for p in neg[:k]],
    )


# Back-compat alias.
# TODO(audit #6): drop once web route migrates to ``build_largest_unrealized``.
build_top_movers = build_largest_unrealized
