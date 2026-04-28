"""Allocation view for the portfolio donut + leaderboard module.

Pure post-processing of an already-priced PositionRow list: ranks holdings by
market value, takes the top-N, aggregates the long tail into a synthetic
'OTHER' slice, and emits concentration stats.

Unpriced positions (market_value is None) are excluded from the allocation —
they have no contribution to a market-share computation by definition. They
still appear in the positions table, just not here.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from net_alpha.portfolio.models import AllocationSlice, AllocationView, PositionRow


def build_allocation(
    *,
    positions: Iterable[PositionRow],
    top_n: int = 10,
    cash: Decimal | None = None,
    cash_pledged: Decimal | None = None,
) -> AllocationView:
    """Build the donut + leaderboard view.

    ``cash`` is the *total* cash balance for the scope. ``cash_pledged`` is
    the portion currently securing open short puts (CSP collateral) and is
    drawn as a separate slice in a slightly muted shade so the user sees the
    free / pledged split without a second chart.
    """
    valued = [p for p in positions if p.market_value is not None and p.market_value > 0]
    valued.sort(key=lambda p: p.market_value or Decimal("0"), reverse=True)

    total = sum((p.market_value for p in valued), start=Decimal("0"))

    has_cash = cash is not None and cash > 0
    grand_total = total + (cash if has_cash else Decimal("0"))

    pledged = cash_pledged if (cash_pledged is not None and cash_pledged > 0 and has_cash) else Decimal("0")
    if has_cash and pledged > cash:
        pledged = cash  # clamp — never report more pledged than total
    free_cash = (cash - pledged) if has_cash else Decimal("0")

    if total <= 0 and not has_cash:
        return AllocationView(
            total_market_value=Decimal("0"),
            symbol_count=0,
            slices=(),
            top1_pct=Decimal("0"),
            top3_pct=Decimal("0"),
            top5_pct=Decimal("0"),
            top10_pct=Decimal("0"),
        )

    head = valued[:top_n]
    tail = valued[top_n:]

    slices: list[AllocationSlice] = []
    for i, pos in enumerate(head, start=1):
        pct = (pos.market_value / grand_total * 100).quantize(Decimal("0.01"))
        slices.append(
            AllocationSlice(
                rank=i,
                symbol=pos.symbol,
                market_value=pos.market_value,
                pct=pct,
                is_rest=False,
            )
        )

    if tail:
        rest_value = sum((p.market_value for p in tail), start=Decimal("0"))
        rest_pct = (rest_value / grand_total * 100).quantize(Decimal("0.01"))
        slices.append(
            AllocationSlice(
                rank=0,
                symbol="OTHER",
                market_value=rest_value,
                pct=rest_pct,
                is_rest=True,
            )
        )

    if has_cash:
        # Free cash slice (always present when has_cash, even if value is 0;
        # we only emit when > 0 to avoid empty entries).
        if free_cash > 0:
            free_pct = (free_cash / grand_total * 100).quantize(Decimal("0.01"))
            slices.append(
                AllocationSlice(
                    rank=0,
                    symbol="Cash",
                    market_value=free_cash,
                    pct=free_pct,
                    is_rest=False,
                    is_cash=True,
                )
            )
        if pledged > 0:
            pledged_pct = (pledged / grand_total * 100).quantize(Decimal("0.01"))
            slices.append(
                AllocationSlice(
                    rank=0,
                    symbol="Pledged",
                    market_value=pledged,
                    pct=pledged_pct,
                    is_rest=False,
                    is_cash=True,
                    is_pledged_cash=True,
                )
            )

    def _share(n: int) -> Decimal:
        s = sum((p.market_value for p in valued[:n]), start=Decimal("0"))
        return (s / grand_total * 100).quantize(Decimal("0.01"))

    return AllocationView(
        total_market_value=grand_total,
        symbol_count=len(valued),
        slices=tuple(slices),
        top1_pct=_share(1),
        top3_pct=_share(3),
        top5_pct=_share(5),
        top10_pct=_share(10),
    )
