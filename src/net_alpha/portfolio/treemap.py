"""Squarified treemap layout — pure layout in Python.

Renders to a list of TreemapTile rectangles in percent coordinates (0–100)
relative to the container. The renderer (Jinja template) just maps these to
inline CSS positions.

Squarified algorithm (Bruls, Huijsen, van Wijk 2000) produces tiles whose
aspect ratios are kept as close to 1 as possible, avoiding the long, thin
slivers that simple slice-and-dice produces when item sizes vary widely.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from net_alpha.portfolio.models import PositionRow, TreemapTile


def build_treemap(*, positions: Iterable[PositionRow], top_n: int = 8) -> list[TreemapTile]:
    """Return tiles laid out via squarified treemap (best aspect ratios)."""
    valued = [p for p in positions if p.market_value is not None and p.market_value > 0]
    valued.sort(key=lambda p: p.market_value or Decimal("0"), reverse=True)
    if not valued:
        return []

    head = valued[:top_n]
    tail = valued[top_n:]
    items: list[tuple[str, Decimal, Decimal | None]] = [(p.symbol, p.market_value, p.unrealized_pl) for p in head]
    if tail:
        other_value = sum((p.market_value for p in tail), start=Decimal("0"))
        other_unrealized: Decimal | None = sum(
            (p.unrealized_pl for p in tail if p.unrealized_pl is not None),
            start=Decimal("0"),
        )
        # If every tail position is unpriced we can't infer P/L; surface as unknown.
        if all(p.unrealized_pl is None for p in tail):
            other_unrealized = None
        items.append(("OTHER", other_value, other_unrealized))

    total = float(sum(v for _, v, _ in items))
    if len(items) == 1:
        sym, val, unr = items[0]
        return [TreemapTile(symbol=sym, market_value=val, unrealized_pl=unr,
                            x_pct=0.0, y_pct=0.0, width_pct=100.0, height_pct=100.0)]

    # Pre-scale values to area-percent so totals remain stable.
    scaled = [(sym, float(val) / total * 100.0 * 100.0, val, unr) for sym, val, unr in items]
    return _squarify(scaled, x=0.0, y=0.0, w=100.0, h=100.0)


def _squarify(
    items: list[tuple[str, float, Decimal, Decimal | None]],
    *,
    x: float,
    y: float,
    w: float,
    h: float,
) -> list[TreemapTile]:
    """Items are (symbol, area_pct_squared, original_value, unrealized).

    `area_pct_squared` is the tile's area in percent² (so they sum to w*h).
    """
    tiles: list[TreemapTile] = []
    remaining = list(items)
    while remaining:
        row, rest = _pick_row(remaining, short_side=min(w, h))
        # Lay out the row along the short side; advance along the long side.
        row_area = sum(a for _, a, _, _ in row)
        if min(w, h) <= 0:
            break
        if w <= h:
            # Row across the top, height = row_area / w
            row_h = row_area / w if w > 0 else 0
            cur_x = x
            for sym, a, val, unr in row:
                tile_w = a / row_h if row_h > 0 else 0
                tiles.append(TreemapTile(
                    symbol=sym, market_value=val, unrealized_pl=unr,
                    x_pct=cur_x, y_pct=y, width_pct=tile_w, height_pct=row_h,
                ))
                cur_x += tile_w
            y += row_h
            h -= row_h
        else:
            row_w = row_area / h if h > 0 else 0
            cur_y = y
            for sym, a, val, unr in row:
                tile_h = a / row_w if row_w > 0 else 0
                tiles.append(TreemapTile(
                    symbol=sym, market_value=val, unrealized_pl=unr,
                    x_pct=x, y_pct=cur_y, width_pct=row_w, height_pct=tile_h,
                ))
                cur_y += tile_h
            x += row_w
            w -= row_w
        remaining = rest
    return tiles


def _pick_row(
    items: list[tuple[str, float, Decimal, Decimal | None]],
    *,
    short_side: float,
) -> tuple[list[tuple[str, float, Decimal, Decimal | None]], list[tuple[str, float, Decimal, Decimal | None]]]:
    """Greedy: keep adding items while the worst aspect ratio improves."""
    row: list[tuple[str, float, Decimal, Decimal | None]] = [items[0]]
    best = _worst_ratio([a for _, a, _, _ in row], short_side)
    for nxt in items[1:]:
        candidate = row + [nxt]
        ratio = _worst_ratio([a for _, a, _, _ in candidate], short_side)
        if ratio < best:
            row = candidate
            best = ratio
        else:
            break
    return row, items[len(row):]


def _worst_ratio(areas: list[float], short_side: float) -> float:
    """Return the worst (largest) aspect ratio in the row for this short side."""
    if not areas or short_side <= 0:
        return float("inf")
    s = sum(areas)
    if s <= 0:
        return float("inf")
    s2 = short_side * short_side
    worst = 0.0
    for a in areas:
        if a <= 0:
            continue
        worst = max(worst, max(s2 * a / (s * s), s * s / (s2 * a)))
    return worst
