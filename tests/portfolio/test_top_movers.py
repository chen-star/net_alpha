from decimal import Decimal

from net_alpha.portfolio.models import PositionRow
from net_alpha.portfolio.top_movers import TopMoversView, build_top_movers


def _row(symbol: str, unrealized: Decimal | None, mv: Decimal | None = Decimal("100")) -> PositionRow:
    return PositionRow(
        symbol=symbol,
        accounts=("Schwab",),
        qty=Decimal("10"),
        market_value=mv,
        open_cost=Decimal("100"),
        avg_basis=Decimal("10"),
        cash_sunk_per_share=Decimal("10"),
        realized_pl=Decimal("0"),
        unrealized_pl=unrealized,
    )


def test_picks_top_3_winners_and_losers_by_dollar():
    rows = [
        _row("A", Decimal("50")),
        _row("B", Decimal("100")),
        _row("C", Decimal("-30")),
        _row("D", Decimal("200")),
        _row("E", Decimal("-500")),
        _row("F", Decimal("10")),
        _row("G", Decimal("-200")),
    ]
    view = build_top_movers(rows, k=3)
    assert [r.symbol for r in view.winners] == ["D", "B", "A"]
    assert [r.symbol for r in view.losers] == ["E", "G", "C"]


def test_excludes_positions_with_no_quote():
    rows = [
        _row("HASMV", Decimal("100"), mv=Decimal("100")),
        _row("NOMV", Decimal("100"), mv=None),
    ]
    view = build_top_movers(rows, k=3)
    assert [r.symbol for r in view.winners] == ["HASMV"]


def test_handles_fewer_than_k_on_each_side():
    rows = [_row("X", Decimal("10")), _row("Y", Decimal("-5"))]
    view = build_top_movers(rows, k=3)
    assert [r.symbol for r in view.winners] == ["X"]
    assert [r.symbol for r in view.losers] == ["Y"]


def test_empty_returns_empty_view():
    view = build_top_movers([], k=3)
    assert view == TopMoversView(winners=[], losers=[])


def test_unrealized_pct_uses_open_cost_when_present():
    row = PositionRow(
        symbol="Z",
        accounts=("Schwab",),
        qty=Decimal("10"),
        market_value=Decimal("150"),
        open_cost=Decimal("100"),
        avg_basis=Decimal("10"),
        cash_sunk_per_share=Decimal("10"),
        realized_pl=Decimal("0"),
        unrealized_pl=Decimal("50"),
    )
    view = build_top_movers([row], k=3)
    assert view.winners[0].unrealized_pct == Decimal("50.0")  # 50 / 100 * 100


def test_unrealized_pct_is_none_when_open_cost_zero():
    row = PositionRow(
        symbol="Z",
        accounts=("Schwab",),
        qty=Decimal("10"),
        market_value=Decimal("150"),
        open_cost=Decimal("0"),
        avg_basis=Decimal("0"),
        cash_sunk_per_share=Decimal("0"),
        realized_pl=Decimal("0"),
        unrealized_pl=Decimal("50"),
    )
    view = build_top_movers([row], k=3)
    assert view.winners[0].unrealized_pct is None
