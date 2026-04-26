from decimal import Decimal

from net_alpha.portfolio.models import PositionRow
from net_alpha.portfolio.treemap import build_treemap


def _row(symbol, value, unrealized=None):
    return PositionRow(
        symbol=symbol,
        accounts=("Tax",),
        qty=Decimal("1"),
        market_value=Decimal(str(value)) if value is not None else None,
        open_cost=Decimal("0"),
        avg_basis=Decimal("0"),
        cash_sunk_per_share=Decimal("0"),
        realized_pl=Decimal("0"),
        unrealized_pl=Decimal(str(unrealized)) if unrealized is not None else None,
    )


def test_empty_input_yields_no_tiles():
    assert build_treemap(positions=[], top_n=5) == []


def test_single_position_fills_entire_area():
    tiles = build_treemap(positions=[_row("SPY", 100, 10)], top_n=5)
    assert len(tiles) == 1
    t = tiles[0]
    assert t.symbol == "SPY"
    assert t.x_pct == 0.0 and t.y_pct == 0.0
    assert abs(t.width_pct - 100.0) < 0.01
    assert abs(t.height_pct - 100.0) < 0.01


def test_top_n_aggregates_long_tail_into_other():
    rows = [_row(s, v) for s, v in [("SPY", 50), ("QQQ", 30), ("AAPL", 10), ("TSLA", 5), ("AMD", 3), ("INTC", 2)]]
    tiles = build_treemap(positions=rows, top_n=3)
    symbols = [t.symbol for t in tiles]
    assert symbols[:3] == ["SPY", "QQQ", "AAPL"]
    assert "OTHER" in symbols
    other = next(t for t in tiles if t.symbol == "OTHER")
    assert other.market_value == Decimal("10")  # 5 + 3 + 2


def test_skips_positions_with_no_market_value():
    tiles = build_treemap(positions=[_row("SPY", None)], top_n=5)
    assert tiles == []


def test_tiles_total_area_approximates_full_box():
    rows = [_row(s, v) for s, v in [("SPY", 60), ("QQQ", 40)]]
    tiles = build_treemap(positions=rows, top_n=5)
    total_area = sum(t.width_pct * t.height_pct for t in tiles) / 100  # in pct² / 100 → pct
    assert abs(total_area - 100.0) < 0.5
