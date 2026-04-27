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
) -> AllocationView:
    valued = [p for p in positions if p.market_value is not None and p.market_value > 0]
    valued.sort(key=lambda p: p.market_value or Decimal("0"), reverse=True)

    total = sum((p.market_value for p in valued), start=Decimal("0"))

    has_cash = cash is not None and cash > 0
    grand_total = total + (cash if has_cash else Decimal("0"))

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
        cash_pct = (cash / grand_total * 100).quantize(Decimal("0.01"))
        slices.append(
            AllocationSlice(
                rank=0,
                symbol="Cash",
                market_value=cash,
                pct=cash_pct,
                is_rest=False,
                is_cash=True,
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
