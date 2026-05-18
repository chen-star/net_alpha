from datetime import date
from decimal import Decimal

from net_alpha.explain.templates import (
    classify_branch,
    confidence_reason,
    disallowed_math_str,
    match_reason_text,
    rule_citation,
)
from net_alpha.models.domain import OptionDetails, Trade


def _t(
    ticker: str,
    action: str,
    *,
    opt: OptionDetails | None = None,
) -> Trade:
    return Trade(
        id="x",
        date=date(2024, 9, 15),
        account="schwab/personal",
        ticker=ticker,
        action=action,
        quantity=1.0,
        proceeds=0.0,
        cost_basis=0.0,
        option_details=opt,
    )


_OPT_A = OptionDetails(strike=100, expiry=date(2025, 1, 17), call_put="C")
_OPT_B = OptionDetails(strike=110, expiry=date(2025, 1, 17), call_put="C")  # differs in strike
_PUT = OptionDetails(strike=100, expiry=date(2025, 1, 17), call_put="P")


def test_classify_branch_equity_equity():
    loss = _t("TSLA", "Sell")
    buy = _t("TSLA", "Buy")
    assert classify_branch(loss, buy) == "equity_equity"


def test_classify_branch_option_option_exact():
    loss = _t("TSLA", "Sell", opt=_OPT_A)
    buy = _t("TSLA", "Buy", opt=_OPT_A)
    assert classify_branch(loss, buy) == "option_option_exact"


def test_classify_branch_option_option_partial_differing_strike():
    loss = _t("TSLA", "Sell", opt=_OPT_A)
    buy = _t("TSLA", "Buy", opt=_OPT_B)
    assert classify_branch(loss, buy) == "option_option_partial"


def test_classify_branch_equity_to_call():
    loss = _t("TSLA", "Sell")
    buy = _t("TSLA", "Buy", opt=_OPT_A)  # buying a call on TSLA
    assert classify_branch(loss, buy) == "equity_to_call"


def test_classify_branch_option_to_equity():
    loss = _t("TSLA", "Sell", opt=_OPT_A)
    buy = _t("TSLA", "Buy")
    assert classify_branch(loss, buy) == "option_to_equity"


def test_classify_branch_etf_pair():
    loss = _t("SPY", "Sell")
    buy = _t("VOO", "Buy")
    assert classify_branch(loss, buy) == "etf_pair"


def test_classify_branch_equity_to_sold_put():
    loss = _t("TSLA", "Sell")
    buy = _t("TSLA", "Sell", opt=_PUT)  # selling a put on TSLA
    assert classify_branch(loss, buy) == "equity_to_sold_put"


def test_classify_branch_unknown_shape_returns_unknown():
    # Loss = equity, buy = long put — matcher returns None; classifier returns 'unknown'
    loss = _t("TSLA", "Sell")
    buy = _t("TSLA", "Buy", opt=_PUT)
    assert classify_branch(loss, buy) == "unknown"


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


def test_match_reason_text_fallback_unknown_kind():
    text = match_reason_text(match_kind="unknown", loss_ticker="AAPL", buy_ticker="MSFT")
    assert "AAPL" in text and "MSFT" in text


def test_confidence_reason_option_chain():
    s = confidence_reason("Unclear", match_kind="option_chain", days_between=8)
    assert "Unclear" in s
    assert "option" in s.lower()
