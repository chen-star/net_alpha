from datetime import date
from decimal import Decimal

from net_alpha.models.domain import HoldingPeriodSuspension, OffsettingGroup, OffsettingPosition
from net_alpha.output.straddles import render_straddles


def _group() -> OffsettingGroup:
    stock = OffsettingPosition(
        kind="long_stock",
        trade_id="t-stk",
        lot_id="lot-stk",
        ticker="AAPL",
        quantity=Decimal("100"),
        opened_at=date(2026, 1, 3),
        side="long",
    )
    put = OffsettingPosition(
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
    return OffsettingGroup(
        account="schwab/personal",
        ticker="AAPL",
        positions=[stock, put],
        kind="married_put",
        confidence="Confirmed",
        rule_citation="IRC §1092(c)(2)(A)",
        reasoning="Long stock paired with long put on same underlying.",
    )


def _suspension() -> HoldingPeriodSuspension:
    return HoldingPeriodSuspension(
        account="schwab/personal",
        ticker="AAPL",
        lot_id="lot-stk",
        suspended_at=date(2026, 1, 10),
        resumed_at=None,
        offsetting_position_kind="long_put",
        rule_citation="IRC §1092(f)",
    )


def test_render_no_groups_says_so():
    out = render_straddles(groups=[], suspensions=[], detail=False)
    assert "no" in out.lower() and "straddle" in out.lower()


def test_render_groups_summary_includes_kind_ticker_account():
    out = render_straddles(groups=[_group()], suspensions=[], detail=False)
    assert "married_put" in out or "married put" in out.lower()
    assert "AAPL" in out
    assert "schwab/personal" in out


def test_render_detail_includes_rule_citation_and_reasoning():
    out = render_straddles(groups=[_group()], suspensions=[], detail=True)
    assert "IRC §1092(c)(2)(A)" in out
    assert "Long stock paired with long put" in out


def test_render_includes_suspensions_when_provided():
    out = render_straddles(groups=[_group()], suspensions=[_suspension()], detail=False)
    assert "suspension" in out.lower() or "suspended" in out.lower()
    assert "§1092(f)" in out
