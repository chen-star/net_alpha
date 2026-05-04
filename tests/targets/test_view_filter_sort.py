from datetime import datetime
from decimal import Decimal

import pytest

from net_alpha.portfolio.models import PositionRow
from net_alpha.targets.models import PositionTarget, TargetUnit
from net_alpha.targets.view import build_plan_view


def _t(symbol: str, dollars: Decimal, tags: tuple[str, ...] = ()) -> PositionTarget:
    return PositionTarget(
        symbol=symbol,
        target_amount=dollars,
        target_unit=TargetUnit.USD,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
        tags=tags,
    )


def _pos(symbol: str, market_value: Decimal, qty: Decimal = Decimal("1")) -> PositionRow:
    return PositionRow(
        symbol=symbol,
        accounts=("Schwab",),
        qty=qty,
        market_value=market_value,
        open_cost=Decimal("0"),
        avg_basis=Decimal("0"),
        cash_sunk_per_share=Decimal("0"),
        realized_pl=Decimal("0"),
        unrealized_pl=Decimal("0"),
    )


@pytest.fixture
def common_targets():
    return [
        _t("AAPL", Decimal("500"), tags=()),
        _t("HIMS", Decimal("1000"), tags=("core", "income")),
        _t("VOO", Decimal("10000"), tags=("core", "etf")),
    ]


@pytest.fixture
def common_quotes():
    return {"AAPL": Decimal("150"), "HIMS": Decimal("100"), "VOO": Decimal("500")}


@pytest.fixture
def common_positions():
    return {
        "AAPL": _pos("AAPL", Decimal("500")),
        "HIMS": _pos("HIMS", Decimal("400")),
        "VOO": _pos("VOO", Decimal("5000")),
    }


def test_default_sort_alpha(common_targets, common_positions, common_quotes):
    pv = build_plan_view(
        targets=common_targets,
        positions_by_symbol=common_positions,
        quotes_by_symbol=common_quotes,
        free_cash=Decimal("0"),
    )
    assert [r.symbol for r in pv.rows] == ["AAPL", "HIMS", "VOO"]
    assert pv.sort_key == "alpha"


def test_sort_by_largest_gap(common_targets, common_positions, common_quotes):
    pv = build_plan_view(
        targets=common_targets,
        positions_by_symbol=common_positions,
        quotes_by_symbol=common_quotes,
        free_cash=Decimal("0"),
        sort_key="gap",
    )
    # Gaps: AAPL 0, HIMS 600, VOO 5000.
    assert [r.symbol for r in pv.rows] == ["VOO", "HIMS", "AAPL"]
    assert pv.sort_key == "gap"


def test_sort_by_lowest_pct_filled(common_targets, common_positions, common_quotes):
    pv = build_plan_view(
        targets=common_targets,
        positions_by_symbol=common_positions,
        quotes_by_symbol=common_quotes,
        free_cash=Decimal("0"),
        sort_key="filled",
    )
    # %: AAPL 100, HIMS 40, VOO 50.
    assert [r.symbol for r in pv.rows] == ["HIMS", "VOO", "AAPL"]


def test_sort_by_highest_target_dollar(common_targets, common_positions, common_quotes):
    pv = build_plan_view(
        targets=common_targets,
        positions_by_symbol=common_positions,
        quotes_by_symbol=common_quotes,
        free_cash=Decimal("0"),
        sort_key="target",
    )
    # Targets: AAPL 500, HIMS 1000, VOO 10000.
    assert [r.symbol for r in pv.rows] == ["VOO", "HIMS", "AAPL"]


def test_invalid_sort_falls_back_to_alpha(common_targets, common_positions, common_quotes):
    pv = build_plan_view(
        targets=common_targets,
        positions_by_symbol=common_positions,
        quotes_by_symbol=common_quotes,
        free_cash=Decimal("0"),
        sort_key="bogus",
    )
    assert [r.symbol for r in pv.rows] == ["AAPL", "HIMS", "VOO"]
    assert pv.sort_key == "alpha"


def test_filter_by_tag_excludes_others(common_targets, common_positions, common_quotes):
    pv = build_plan_view(
        targets=common_targets,
        positions_by_symbol=common_positions,
        quotes_by_symbol=common_quotes,
        free_cash=Decimal("0"),
        selected_tag="core",
    )
    assert [r.symbol for r in pv.rows] == ["HIMS", "VOO"]
    assert pv.selected_tag == "core"
    by_tag = {s.tag: s for s in pv.tag_summaries}
    # tag_summaries computed pre-filter — full set still present.
    assert "core" in by_tag and "income" in by_tag and "untagged" in by_tag


def test_filter_untagged(common_targets, common_positions, common_quotes):
    pv = build_plan_view(
        targets=common_targets,
        positions_by_symbol=common_positions,
        quotes_by_symbol=common_quotes,
        free_cash=Decimal("0"),
        selected_tag="untagged",
    )
    assert [r.symbol for r in pv.rows] == ["AAPL"]


def test_unknown_tag_falls_back_to_all(common_targets, common_positions, common_quotes):
    pv = build_plan_view(
        targets=common_targets,
        positions_by_symbol=common_positions,
        quotes_by_symbol=common_quotes,
        free_cash=Decimal("0"),
        selected_tag="nonexistent",
    )
    assert [r.symbol for r in pv.rows] == ["AAPL", "HIMS", "VOO"]
    assert pv.selected_tag is None
