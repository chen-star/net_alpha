from datetime import date
from decimal import Decimal

from net_alpha.explain import ExplanationModel, TradeRow
from net_alpha.explain.cli_renderer import render_explanation


def _model(is_exempt=False):
    return ExplanationModel(
        summary="TSLA loss on 2024-09-15 disallowed by buy on 2024-09-22 (7 days later).",
        rule_citation="IRC §1091(a) — Pub 550 p.59",
        is_exempt=is_exempt,
        loss_trade=TradeRow(date=date(2024, 9, 15), ticker="TSLA", action="Sell",
                            quantity=100, proceeds=Decimal("18757"), cost_basis=Decimal("20000")),
        triggering_buy=TradeRow(date=date(2024, 9, 22), ticker="TSLA", action="Buy",
                                quantity=100, proceeds=Decimal("19000"), cost_basis=Decimal("19000")),
        days_between=7,
        match_reason="exact ticker — TSLA",
        disallowed_or_notional=Decimal("1243"),
        disallowed_math="$1,243.00",
        confidence="Confirmed",
        confidence_reason="Confirmed — exact ticker match within 7 days",
        adjusted_basis_target=None,
        cross_account=None,
    )


def test_render_explanation_violation_includes_all_fields():
    out = render_explanation(_model())
    assert "TSLA" in out
    assert "IRC §1091(a)" in out
    assert "$1,243.00" in out
    assert "Confirmed" in out
    assert "exact ticker" in out


def test_render_explanation_exempt_uses_exempt_copy():
    m = _model(is_exempt=True)
    m.rule_citation = "IRC §1256(c)"
    m.summary = "SPX match — exempt under §1256(c)."
    out = render_explanation(m)
    assert "§1256(c)" in out
    assert "exempt" in out.lower()


def test_render_explanation_partial_match_shows_math():
    m = _model()
    m.disallowed_math = "$1,243.00 × (50 / 100) = $621.50"
    out = render_explanation(m)
    assert "× (50 / 100)" in out or "(50 / 100)" in out
    assert "$621.50" in out
