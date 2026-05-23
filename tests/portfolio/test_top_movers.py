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


def test_largest_unrealized_alias_exposes_clarified_naming():
    """Audit #6: panel called 'Top Movers' but ranks by *lifetime*
    unrealized P&L since acquisition — not a session/1-day window.
    The clarified name is 'Largest unrealized gains/losses'. Expose
    ``build_largest_unrealized`` (function), ``LargestUnrealizedView``
    (model), and ``gains`` / ``losses`` fields as the primary names —
    keep ``build_top_movers`` / ``TopMoversView`` / ``winners`` /
    ``losers`` as back-compat aliases so callers (web route + template)
    don't break in this commit.
    """
    from net_alpha.portfolio.top_movers import (
        LargestUnrealizedView,
        TopMoversView,
        build_largest_unrealized,
        build_top_movers,
    )

    # The aliases point at the same callables / classes.
    assert build_largest_unrealized is build_top_movers
    assert LargestUnrealizedView is TopMoversView

    rows = [_row("A", Decimal("50")), _row("B", Decimal("-30"))]
    view = build_largest_unrealized(rows, k=3)
    # Primary, clarified field names.
    assert [r.symbol for r in view.gains] == ["A"]
    assert [r.symbol for r in view.losses] == ["B"]
    # Back-compat aliases continue to work for now.
    assert view.winners == view.gains
    assert view.losers == view.losses


def test_largest_unrealized_ranking_is_unchanged_by_rename():
    """Pure rename: the underlying ranking by absolute lifetime unrealized
    P&L is the same data the pre-fix function returned.
    """
    from net_alpha.portfolio.top_movers import build_largest_unrealized

    rows = [
        _row("A", Decimal("50")),
        _row("B", Decimal("100")),
        _row("C", Decimal("-30")),
        _row("D", Decimal("200")),
        _row("E", Decimal("-500")),
    ]
    view = build_largest_unrealized(rows, k=3)
    assert [r.symbol for r in view.gains] == ["D", "B", "A"]
    assert [r.symbol for r in view.losses] == ["E", "C"]


def test_top_movers_module_docstring_clarifies_ranking_window():
    """The module docstring must NOT imply a session / 1-day window — the
    ranking is over lifetime unrealized P&L since the position was opened.
    """
    import net_alpha.portfolio.top_movers as tm

    doc = (tm.__doc__ or "") + (build_top_movers.__doc__ or "")
    assert "lifetime" in doc.lower()
