"""Slice-and-dice treemap layout — pure layout in Python.

Renders to a list of TreemapTile rectangles in percent coordinates (0–100)
relative to the container. The renderer (Jinja template) just maps these to
inline CSS positions.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from net_alpha.portfolio.models import PositionRow, TreemapTile


def build_treemap(*, positions: Iterable[PositionRow], top_n: int = 8) -> list[TreemapTile]:
    """Return tiles laid out via simple slice-and-dice (alternating split direction)."""
    valued = [p for p in positions if p.market_value is not None and p.market_value > 0]
    valued.sort(key=lambda p: p.market_value or Decimal("0"), reverse=True)
    if not valued:
        return []

    head = valued[:top_n]
    tail = valued[top_n:]
    items: list[tuple[str, Decimal, Decimal | None]] = [(p.symbol, p.market_value, p.unrealized_pl) for p in head]
    if tail:
        other_value = sum((p.market_value for p in tail), start=Decimal("0"))
        other_unrealized = sum(
            (p.unrealized_pl for p in tail if p.unrealized_pl is not None),
            start=Decimal("0"),
        )
        items.append(("OTHER", other_value, other_unrealized))

    total = sum(v for _, v, _ in items)
    return _layout(items, x=0.0, y=0.0, w=100.0, h=100.0, total=float(total), horizontal=True)


def _layout(
    items: list[tuple[str, Decimal, Decimal | None]],
    *,
    x: float,
    y: float,
    w: float,
    h: float,
    total: float,
    horizontal: bool,
) -> list[TreemapTile]:
    if not items or total <= 0:
        return []
    if len(items) == 1:
        sym, val, unr = items[0]
        return [
            TreemapTile(
                symbol=sym,
                market_value=val,
                unrealized_pl=unr,
                x_pct=x,
                y_pct=y,
                width_pct=w,
                height_pct=h,
            )
        ]
    # Take the largest item, place it in a slice, recurse on the remainder.
    sym, val, unr = items[0]
    rest = items[1:]
    fraction = float(val) / total
    if horizontal:
        slice_w = w * fraction
        first = TreemapTile(
            symbol=sym, market_value=val, unrealized_pl=unr, x_pct=x, y_pct=y, width_pct=slice_w, height_pct=h
        )
        rest_total = total - float(val)
        return [first] + _layout(rest, x=x + slice_w, y=y, w=w - slice_w, h=h, total=rest_total, horizontal=False)
    else:
        slice_h = h * fraction
        first = TreemapTile(
            symbol=sym, market_value=val, unrealized_pl=unr, x_pct=x, y_pct=y, width_pct=w, height_pct=slice_h
        )
        rest_total = total - float(val)
        return [first] + _layout(rest, x=x, y=y + slice_h, w=w, h=h - slice_h, total=rest_total, horizontal=True)
