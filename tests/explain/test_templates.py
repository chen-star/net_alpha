from decimal import Decimal

from net_alpha.explain.templates import (
    confidence_reason,
    disallowed_math_str,
    match_reason_text,
    rule_citation,
)


def test_rule_citation_for_regular_violation():
    assert rule_citation("regular") == "IRC §1091(a) — Pub 550 p.59"


def test_rule_citation_for_section_1256():
    assert rule_citation("section_1256") == "IRC §1256(c)"


def test_match_reason_text_exact_ticker():
    text = match_reason_text(match_kind="exact_ticker", loss_ticker="TSLA", buy_ticker="TSLA")
    assert "exact ticker" in text.lower()
    assert "TSLA" in text


def test_match_reason_text_etf_pair():
    text = match_reason_text(match_kind="etf_pair", loss_ticker="SPY", buy_ticker="VOO", group="sp500")
    assert "ETF pair" in text
    assert "SPY" in text and "VOO" in text


def test_match_reason_text_option_chain():
    text = match_reason_text(
        match_kind="option_chain",
        loss_ticker="TSLA",
        buy_ticker="TSLA",
        option_details="TSLA 250C 2024-12-20",
    )
    assert "option" in text.lower()
    assert "250C" in text


def test_disallowed_math_str_partial():
    s = disallowed_math_str(loss=Decimal("1243"), allocable_qty=50, loss_qty=100)
    assert "$1,243" in s
    assert "50" in s
    assert "100" in s
    assert "$621.50" in s


def test_disallowed_math_str_full():
    s = disallowed_math_str(loss=Decimal("1243"), allocable_qty=100, loss_qty=100)
    assert "$1,243" in s


def test_confidence_reason_confirmed_exact_ticker():
    s = confidence_reason("Confirmed", match_kind="exact_ticker", days_between=4)
    assert "Confirmed" in s
    assert "exact ticker" in s.lower() or "ticker" in s.lower()
    assert "4 days" in s


def test_confidence_reason_probable():
    s = confidence_reason("Probable", match_kind="etf_pair", days_between=12)
    assert "Probable" in s
