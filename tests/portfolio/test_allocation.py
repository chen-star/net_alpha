from decimal import Decimal

from net_alpha.portfolio.allocation import build_allocation
from net_alpha.portfolio.models import PositionRow


def _row(symbol: str, value: float | None) -> PositionRow:
    return PositionRow(
        symbol=symbol,
        accounts=("A",),
        qty=Decimal("1"),
        market_value=Decimal(str(value)) if value is not None else None,
        open_cost=Decimal("0"),
        avg_basis=Decimal("0"),
        cash_sunk_per_share=Decimal("0"),
        realized_pl=Decimal("0"),
        unrealized_pl=None,
    )


def test_empty_input_yields_empty_view():
    view = build_allocation(positions=[], top_n=10)
    assert view.total_market_value == Decimal("0")
    assert view.symbol_count == 0
    assert view.slices == ()
    assert view.top1_pct == Decimal("0")


def test_top_n_smaller_than_positions_aggregates_rest():
    rows = [
        _row(s, v)
        for s, v in [
            ("AAA", 100),
            ("BBB", 60),
            ("CCC", 30),
            ("DDD", 6),
            ("EEE", 4),
        ]
    ]
    view = build_allocation(positions=rows, top_n=3)

    assert view.symbol_count == 5
    assert view.total_market_value == Decimal("200")

    # Slices: AAA, BBB, CCC, OTHER
    assert len(view.slices) == 4
    syms = [s.symbol for s in view.slices]
    assert syms == ["AAA", "BBB", "CCC", "OTHER"]

    aaa = view.slices[0]
    assert aaa.rank == 1
    assert aaa.market_value == Decimal("100")
    assert aaa.pct == Decimal("50.00")
    assert not aaa.is_rest

    rest = view.slices[-1]
    assert rest.is_rest
    assert rest.market_value == Decimal("10")  # 6 + 4
    assert rest.pct == Decimal("5.00")


def test_top_n_equal_to_positions_no_rest_slice():
    rows = [_row("X", 70), _row("Y", 30)]
    view = build_allocation(positions=rows, top_n=10)
    assert len(view.slices) == 2
    assert all(not s.is_rest for s in view.slices)


def test_concentration_stats():
    rows = [_row(f"S{i}", v) for i, v in enumerate([40, 25, 15, 10, 5, 3, 2])]
    view = build_allocation(positions=rows, top_n=10)
    assert view.top1_pct == Decimal("40.00")
    assert view.top3_pct == Decimal("80.00")
    assert view.top5_pct == Decimal("95.00")
    # Only 7 positions, so top10 = 100
    assert view.top10_pct == Decimal("100.00")


def test_unpriced_positions_are_excluded_from_total():
    rows = [_row("PRICED", 100), _row("UNPRICED", None)]
    view = build_allocation(positions=rows, top_n=10)
    assert view.total_market_value == Decimal("100")
    assert view.symbol_count == 1  # only priced positions count toward allocation
    assert len(view.slices) == 1
    assert view.slices[0].symbol == "PRICED"


def test_zero_total_yields_zero_pct_no_division_error():
    rows = [_row("Z", 0)]
    view = build_allocation(positions=rows, top_n=10)
    assert view.total_market_value == Decimal("0")
    assert view.slices == ()


def test_allocation_includes_cash_slice_when_provided():
    pos = _row("SPY", 750)
    alloc = build_allocation(positions=[pos], top_n=10, cash=Decimal("250"))
    cash_slices = [s for s in alloc.slices if s.is_cash]
    assert len(cash_slices) == 1
    assert cash_slices[0].symbol == "Cash"
    assert cash_slices[0].market_value == Decimal("250")
    # 250 / (750 + 250) = 25%
    assert cash_slices[0].pct == Decimal("25.00")
    # SPY is now 75% of total
    spy_slice = next(s for s in alloc.slices if s.symbol == "SPY")
    assert spy_slice.pct == Decimal("75.00")


def test_allocation_omits_cash_slice_when_zero():
    alloc = build_allocation(positions=[], top_n=10, cash=Decimal("0"))
    assert all(not s.is_cash for s in alloc.slices)


def test_allocation_omits_cash_slice_when_none():
    pos = _row("SPY", 100)
    alloc = build_allocation(positions=[pos], top_n=10)  # no cash kwarg
    assert all(not s.is_cash for s in alloc.slices)
    assert alloc.total_market_value == Decimal("100")  # unchanged behavior
