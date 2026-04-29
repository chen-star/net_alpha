from datetime import date, datetime
from decimal import Decimal

from net_alpha.portfolio.models import PositionRow
from net_alpha.targets.models import PositionTarget, TargetUnit
from net_alpha.targets.view import PlanRow, PlanView, build_plan_view


def _target(sym: str, amount: str, unit: TargetUnit) -> PositionTarget:
    return PositionTarget(
        symbol=sym,
        target_amount=Decimal(amount),
        target_unit=unit,
        created_at=datetime(2026, 4, 1),
        updated_at=datetime(2026, 4, 1),
    )


def _pos(sym: str, qty: str, mv: str) -> PositionRow:
    return PositionRow(
        symbol=sym, accounts=("Schwab",),
        qty=Decimal(qty), market_value=Decimal(mv),
        open_cost=Decimal("0"),
        avg_basis=Decimal("0"), cash_sunk_per_share=Decimal("0"),
        realized_pl=Decimal("0"), unrealized_pl=Decimal("0"),
    )


def test_usd_target_with_quote_computes_share_equiv_and_gap():
    target = _target("HIMS", "1000", TargetUnit.USD)
    pos = _pos("HIMS", "26.6", "800")  # 800 / 26.6 ≈ 30.07/sh
    view = build_plan_view(
        targets=[target],
        positions_by_symbol={"HIMS": pos},
        quotes_by_symbol={"HIMS": Decimal("30.04")},
        free_cash=Decimal("5000"),
    )
    row = view.rows[0]
    assert row.symbol == "HIMS"
    assert row.target_dollar_equiv == Decimal("1000")
    assert row.target_share_equiv == Decimal("33.29")  # 1000 / 30.04, qtz to .01
    assert row.current_dollar == Decimal("800")
    assert row.gap_dollar == Decimal("200")
    assert row.pct_filled == Decimal("80.00")  # 800/1000


def test_share_target_with_quote_computes_dollar_equiv():
    target = _target("SPY", "50", TargetUnit.SHARES)
    pos = _pos("SPY", "42", "20580")
    view = build_plan_view(
        targets=[target],
        positions_by_symbol={"SPY": pos},
        quotes_by_symbol={"SPY": Decimal("490")},
        free_cash=Decimal("5000"),
    )
    row = view.rows[0]
    assert row.target_share_equiv == Decimal("50")
    assert row.target_dollar_equiv == Decimal("24500.00")  # 50 × 490
    assert row.gap_shares == Decimal("8")
    assert row.pct_filled == Decimal("84.00")  # 42/50


def test_wishlist_zero_current():
    target = _target("MSFT", "5000", TargetUnit.USD)
    view = build_plan_view(
        targets=[target],
        positions_by_symbol={},  # not held
        quotes_by_symbol={"MSFT": Decimal("384.10")},
        free_cash=Decimal("100"),
    )
    row = view.rows[0]
    assert row.current_dollar == Decimal("0")
    assert row.current_shares == Decimal("0")
    assert row.gap_dollar == Decimal("5000")
    assert row.pct_filled == Decimal("0.00")


def test_over_target_yields_negative_gap_and_pct_above_100():
    target = _target("VOO", "10000", TargetUnit.USD)
    pos = _pos("VOO", "24", "11200")
    view = build_plan_view(
        targets=[target],
        positions_by_symbol={"VOO": pos},
        quotes_by_symbol={"VOO": Decimal("466.66")},
        free_cash=Decimal("100"),
    )
    row = view.rows[0]
    assert row.gap_dollar == Decimal("-1200")
    assert row.pct_filled == Decimal("112.00")


def test_alphabetical_order():
    targets = [
        _target("VOO", "10000", TargetUnit.USD),
        _target("AAPL", "1000", TargetUnit.USD),
        _target("MSFT", "5000", TargetUnit.USD),
    ]
    view = build_plan_view(
        targets=targets, positions_by_symbol={}, quotes_by_symbol={},
        free_cash=Decimal("0"),
    )
    assert [r.symbol for r in view.rows] == ["AAPL", "MSFT", "VOO"]


def test_total_to_fill_excludes_over_target_rows():
    targets = [
        _target("HIMS", "1000", TargetUnit.USD),  # gap +200
        _target("VOO", "10000", TargetUnit.USD),  # gap -1200 (over target)
    ]
    positions = {
        "HIMS": _pos("HIMS", "26.6", "800"),
        "VOO":  _pos("VOO", "24", "11200"),
    }
    view = build_plan_view(
        targets=targets,
        positions_by_symbol=positions,
        quotes_by_symbol={"HIMS": Decimal("30.04"), "VOO": Decimal("466.66")},
        free_cash=Decimal("5000"),
    )
    assert view.total_to_fill_dollar == Decimal("200")  # over-target excluded
    assert view.coverage_pct == Decimal("2500.00")      # 5000/200*100 = uncapped


def test_missing_quote_keeps_native_unit_only():
    target = _target("OBSCURE", "1000", TargetUnit.USD)
    view = build_plan_view(
        targets=[target], positions_by_symbol={}, quotes_by_symbol={},
        free_cash=Decimal("0"),
    )
    row = view.rows[0]
    assert row.target_dollar_equiv == Decimal("1000")
    assert row.target_share_equiv is None
    assert row.last_price is None


def test_coverage_none_when_total_to_fill_is_zero():
    target = _target("SPY", "50", TargetUnit.SHARES)
    pos = _pos("SPY", "50", "24500")  # exactly at target
    view = build_plan_view(
        targets=[target], positions_by_symbol={"SPY": pos},
        quotes_by_symbol={"SPY": Decimal("490")},
        free_cash=Decimal("5000"),
    )
    assert view.total_to_fill_dollar == Decimal("0")
    assert view.coverage_pct is None
