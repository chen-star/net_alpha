from datetime import date
from decimal import Decimal

from net_alpha.models.domain import OffsettingGroup, OffsettingPosition
from net_alpha.section_1092.holding_period import compute_suspensions


def _stock_pos() -> OffsettingPosition:
    return OffsettingPosition(
        kind="long_stock",
        trade_id="t-stock",
        lot_id="lot-stock",
        ticker="AAPL",
        quantity=Decimal("100"),
        opened_at=date(2026, 1, 3),
        side="long",
    )


def _put_pos() -> OffsettingPosition:
    return OffsettingPosition(
        kind="long_put",
        trade_id="t-put",
        lot_id="lot-put",
        ticker="AAPL",
        quantity=Decimal("1"),
        opened_at=date(2026, 1, 10),
        side="long",
        option_strike=Decimal("180"),
        option_expiry=date(2026, 6, 19),
        option_call_put="P",
    )


def test_no_groups_no_suspensions():
    assert compute_suspensions([]) == []


def test_married_put_suspends_stock_holding_period():
    g = OffsettingGroup(
        account="schwab/personal",
        ticker="AAPL",
        positions=[_stock_pos(), _put_pos()],
        kind="married_put",
        confidence="Confirmed",
        rule_citation="IRC §1092(c)(2)(A)",
        reasoning="r",
    )
    sus = compute_suspensions([g])
    assert len(sus) == 1
    assert sus[0].lot_id == "lot-stock"
    # Suspension begins on the LATER of the two open dates (when the offset began).
    assert sus[0].suspended_at == date(2026, 1, 10)
    assert sus[0].resumed_at is None
    assert sus[0].rule_citation == "IRC §1092(f)"


def test_short_option_legs_dont_get_suspension_records():
    # Short legs have no lot_id and no LT clock to suspend in v1.
    short = OffsettingPosition(
        kind="short_call",
        trade_id="t-sc",
        lot_id=None,
        ticker="AAPL",
        quantity=Decimal("1"),
        opened_at=date(2026, 1, 15),
        side="short",
        option_strike=Decimal("200"),
        option_expiry=date(2026, 6, 19),
        option_call_put="C",
    )
    g = OffsettingGroup(
        account="schwab/personal",
        ticker="AAPL",
        positions=[_stock_pos(), short],
        kind="covered_call",
        confidence="Confirmed",
        rule_citation="IRC §1092(c)(4)",
        reasoning="r",
    )
    sus = compute_suspensions([g])
    # One suspension on the long stock; none on the short call.
    assert [s.lot_id for s in sus] == ["lot-stock"]
