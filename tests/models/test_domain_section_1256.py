from datetime import date, datetime
from decimal import Decimal

import pytest

from net_alpha.models.domain import (
    DetectionResult,
    ExemptMatch,
    OptionDetails,
    Section1256Classification,
    Trade,
    WashSaleViolation,
)


def test_exempt_match_required_fields():
    em = ExemptMatch(
        loss_trade_id="t-loss",
        triggering_buy_id="t-buy",
        exempt_reason="section_1256",
        rule_citation="IRC §1256(c)",
        notional_disallowed=Decimal("621.50"),
        confidence="Confirmed",
        matched_quantity=50,
        loss_account="schwab/personal",
        buy_account="schwab/personal",
        loss_sale_date=date(2024, 9, 15),
        triggering_buy_date=date(2024, 9, 22),
        ticker="SPX",
    )
    assert em.exempt_reason == "section_1256"
    assert em.notional_disallowed == Decimal("621.50")


def test_section_1256_classification_60_40_split():
    c = Section1256Classification(
        trade_id="t-spx-close",
        realized_pnl=Decimal("1000"),
        long_term_portion=Decimal("600"),
        short_term_portion=Decimal("400"),
        underlying="SPX",
    )
    assert c.long_term_portion + c.short_term_portion == c.realized_pnl


def test_trade_is_section_1256_default_false():
    t = Trade(
        id="t1",
        date=date.today(),
        account="x",
        ticker="AAPL",
        action="buy",
        quantity=10,
        proceeds=100,
        cost_basis=100,
        option_details=None,
    )
    assert t.is_section_1256 is False


def test_trade_is_section_1256_can_be_set():
    t = Trade(
        id="t1",
        date=date.today(),
        account="x",
        ticker="SPX",
        action="buy",
        quantity=1,
        proceeds=100,
        cost_basis=100,
        option_details=OptionDetails(strike=4500, expiry=date(2025, 12, 19), call_put="C"),
        is_section_1256=True,
    )
    assert t.is_section_1256 is True


def test_detection_result_carries_exempt_matches():
    result = DetectionResult(violations=[], lots=[], exempt_matches=[])
    assert result.exempt_matches == []
