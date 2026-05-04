"""Tag-aware additions to PlanView. Sort/filter live in test_view_filter_sort."""

from datetime import datetime
from decimal import Decimal

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


def test_plan_view_exposes_all_tags_alpha_sorted():
    pv = build_plan_view(
        targets=[
            _t("HIMS", Decimal("1000"), tags=("income", "core")),
            _t("VOO", Decimal("10000"), tags=("etf", "core")),
            _t("AAPL", Decimal("500"), tags=()),  # untagged
        ],
        positions_by_symbol={},
        quotes_by_symbol={},
        free_cash=Decimal("0"),
    )
    assert pv.all_tags == ("core", "etf", "income")


def test_plan_view_tag_summary_counts_overlap():
    """A target with two tags counts in BOTH summaries."""
    targets = [
        _t("HIMS", Decimal("1000"), tags=("core", "income")),
        _t("VOO", Decimal("10000"), tags=("core", "etf")),
    ]
    positions = {
        "HIMS": _pos("HIMS", Decimal("400")),
        "VOO": _pos("VOO", Decimal("5000")),
    }
    pv = build_plan_view(
        targets=targets,
        positions_by_symbol=positions,
        quotes_by_symbol={"HIMS": Decimal("100"), "VOO": Decimal("500")},
        free_cash=Decimal("0"),
    )
    by_tag = {s.tag: s for s in pv.tag_summaries}
    assert by_tag["core"].target_count == 2
    assert by_tag["core"].current_dollar == Decimal("5400.00")
    assert by_tag["core"].gap_to_fill_dollar == Decimal("5600.00")
    assert by_tag["income"].target_count == 1
    assert by_tag["income"].current_dollar == Decimal("400.00")
    assert by_tag["etf"].target_count == 1
    assert by_tag["etf"].current_dollar == Decimal("5000.00")


def test_plan_view_untagged_bucket_present_only_when_used():
    pv_with = build_plan_view(
        targets=[_t("AAPL", Decimal("500"), tags=())],
        positions_by_symbol={},
        quotes_by_symbol={"AAPL": Decimal("150")},
        free_cash=Decimal("0"),
    )
    assert any(s.tag == "untagged" for s in pv_with.tag_summaries)

    pv_without = build_plan_view(
        targets=[_t("AAPL", Decimal("500"), tags=("core",))],
        positions_by_symbol={},
        quotes_by_symbol={"AAPL": Decimal("150")},
        free_cash=Decimal("0"),
    )
    assert not any(s.tag == "untagged" for s in pv_without.tag_summaries)


def test_plan_view_tag_summary_planned_dollar_none_when_quote_missing():
    # Force a row whose target_dollar_equiv is None: a SHARES-target with no quote.
    targets = [
        PositionTarget(
            symbol="OBSCURE",
            target_amount=Decimal("10"),
            target_unit=TargetUnit.SHARES,
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1),
            tags=("core",),
        ),
    ]
    pv = build_plan_view(
        targets=targets,
        positions_by_symbol={},
        quotes_by_symbol={},  # no quote at all
        free_cash=Decimal("0"),
    )
    by_tag = {s.tag: s for s in pv.tag_summaries}
    assert by_tag["core"].planned_dollar is None


def test_plan_view_tag_summaries_sorted_with_untagged_last():
    pv = build_plan_view(
        targets=[
            _t("VOO", Decimal("10000"), tags=("zeta",)),
            _t("HIMS", Decimal("1000"), tags=("alpha",)),
            _t("AAPL", Decimal("500"), tags=()),
        ],
        positions_by_symbol={},
        quotes_by_symbol={},
        free_cash=Decimal("0"),
    )
    tags_in_order = [s.tag for s in pv.tag_summaries]
    assert tags_in_order == ["alpha", "zeta", "untagged"]


def test_plan_row_carries_tags():
    targets = [_t("HIMS", Decimal("1000"), tags=("core", "income"))]
    pv = build_plan_view(
        targets=targets,
        positions_by_symbol={},
        quotes_by_symbol={"HIMS": Decimal("100")},
        free_cash=Decimal("0"),
    )
    assert pv.rows[0].tags == ("core", "income")
