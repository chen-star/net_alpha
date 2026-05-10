from datetime import date
from decimal import Decimal

from net_alpha.models.domain import HoldingPeriodSuspension, OffsettingGroup, OffsettingPosition


def test_offsetting_position_basic_construction():
    p = OffsettingPosition(
        kind="long_stock",
        trade_id="trade-abc",
        lot_id="lot-abc",
        ticker="AAPL",
        quantity=Decimal("100"),
        opened_at=date(2026, 1, 5),
        side="long",
    )
    assert p.kind == "long_stock"
    assert p.side == "long"
    assert p.option_strike is None


def test_offsetting_position_with_option_details():
    p = OffsettingPosition(
        kind="long_put",
        trade_id="trade-put",
        lot_id="lot-put",
        ticker="AAPL",
        quantity=Decimal("1"),
        opened_at=date(2026, 1, 10),
        side="long",
        option_strike=Decimal("180"),
        option_expiry=date(2026, 6, 19),
        option_call_put="P",
    )
    assert p.option_strike == Decimal("180")
    assert p.option_call_put == "P"


def test_offsetting_group_carries_rule_metadata():
    pos = OffsettingPosition(
        kind="long_stock",
        trade_id="t1",
        lot_id="l1",
        ticker="AAPL",
        quantity=Decimal("100"),
        opened_at=date(2026, 1, 5),
        side="long",
    )
    g = OffsettingGroup(
        account="schwab/personal",
        ticker="AAPL",
        positions=[pos, pos],
        kind="married_put",
        confidence="Confirmed",
        rule_citation="IRC §1092(c)(2)(A)",
        reasoning="Long stock and long put on same underlying",
    )
    assert g.kind == "married_put"
    assert g.confidence == "Confirmed"
    assert g.rule_citation.startswith("IRC §1092")


def test_holding_period_suspension_carries_dates():
    s = HoldingPeriodSuspension(
        account="schwab/personal",
        ticker="AAPL",
        lot_id="lot-stock",
        suspended_at=date(2026, 1, 10),
        resumed_at=None,
        offsetting_position_kind="long_put",
        rule_citation="IRC §1092(f)",
    )
    assert s.resumed_at is None
    assert s.suspended_at == date(2026, 1, 10)
