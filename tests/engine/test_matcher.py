from datetime import date

from net_alpha.engine.matcher import get_match_confidence, is_within_wash_sale_window
from net_alpha.models.domain import OptionDetails, Trade


def test_same_day():
    assert is_within_wash_sale_window(date(2024, 10, 15), date(2024, 10, 15)) is True


def test_exactly_30_days_before():
    assert is_within_wash_sale_window(date(2024, 10, 15), date(2024, 9, 15)) is True


def test_exactly_30_days_after():
    assert is_within_wash_sale_window(date(2024, 10, 15), date(2024, 11, 14)) is True


def test_31_days_before_outside_window():
    assert is_within_wash_sale_window(date(2024, 10, 15), date(2024, 9, 14)) is False


def test_31_days_after_outside_window():
    assert is_within_wash_sale_window(date(2024, 10, 15), date(2024, 11, 15)) is False


def test_1_day_before():
    assert is_within_wash_sale_window(date(2024, 10, 15), date(2024, 10, 14)) is True


def test_1_day_after():
    assert is_within_wash_sale_window(date(2024, 10, 15), date(2024, 10, 16)) is True


def test_cross_year_boundary():
    # Dec 20 sale, Jan 5 buy = 16 days → within window
    assert is_within_wash_sale_window(date(2024, 12, 20), date(2025, 1, 5)) is True


def test_cross_year_boundary_outside():
    # Dec 1 sale, Jan 31 buy = 61 days → outside window
    assert is_within_wash_sale_window(date(2024, 12, 1), date(2025, 1, 31)) is False


# --- Equity confidence tests (Task 6) ---


def test_equity_same_ticker_confirmed():
    sell = Trade(
        account="A",
        date=date(2024, 1, 1),
        ticker="TSLA",
        action="Sell",
        quantity=10.0,
        proceeds=2000.0,
        cost_basis=3000.0,
    )
    buy = Trade(
        account="B",
        date=date(2024, 1, 10),
        ticker="TSLA",
        action="Buy",
        quantity=10.0,
        cost_basis=2500.0,
    )
    assert get_match_confidence(sell, buy, {}) == "Confirmed"


def test_equity_different_ticker_no_match():
    sell = Trade(
        account="A",
        date=date(2024, 1, 1),
        ticker="TSLA",
        action="Sell",
        quantity=10.0,
        proceeds=2000.0,
        cost_basis=3000.0,
    )
    buy = Trade(
        account="B",
        date=date(2024, 1, 10),
        ticker="AAPL",
        action="Buy",
        quantity=10.0,
        cost_basis=2500.0,
    )
    assert get_match_confidence(sell, buy, {}) is None


def test_non_buy_candidate_no_match():
    sell = Trade(
        account="A",
        date=date(2024, 1, 1),
        ticker="TSLA",
        action="Sell",
        quantity=10.0,
        proceeds=2000.0,
        cost_basis=3000.0,
    )
    other_sell = Trade(
        account="B",
        date=date(2024, 1, 10),
        ticker="TSLA",
        action="Sell",
        quantity=10.0,
        proceeds=2500.0,
        cost_basis=2000.0,
    )
    assert get_match_confidence(sell, other_sell, {}) is None


# --- Option confidence tests (Task 7) ---


def test_option_same_option_confirmed():
    """Sold option at loss, bought same option (same strike/expiry)."""
    sell = Trade(
        account="A",
        date=date(2024, 1, 1),
        ticker="TSLA",
        action="Sell",
        quantity=1.0,
        proceeds=200.0,
        cost_basis=500.0,
        option_details=OptionDetails(strike=250.0, expiry=date(2024, 12, 20), call_put="C"),
    )
    buy = Trade(
        account="B",
        date=date(2024, 1, 10),
        ticker="TSLA",
        action="Buy",
        quantity=1.0,
        cost_basis=450.0,
        option_details=OptionDetails(strike=250.0, expiry=date(2024, 12, 20), call_put="C"),
    )
    assert get_match_confidence(sell, buy, {}) == "Confirmed"


def test_option_different_strike_probable():
    """Sold option at loss, bought option on same underlying (different strike)."""
    sell = Trade(
        account="A",
        date=date(2024, 1, 1),
        ticker="TSLA",
        action="Sell",
        quantity=1.0,
        proceeds=200.0,
        cost_basis=500.0,
        option_details=OptionDetails(strike=250.0, expiry=date(2024, 12, 20), call_put="C"),
    )
    buy = Trade(
        account="B",
        date=date(2024, 1, 10),
        ticker="TSLA",
        action="Buy",
        quantity=1.0,
        cost_basis=600.0,
        option_details=OptionDetails(strike=300.0, expiry=date(2024, 12, 20), call_put="C"),
    )
    assert get_match_confidence(sell, buy, {}) == "Probable"


def test_option_different_expiry_probable():
    """Sold option at loss, bought option on same underlying (different expiry)."""
    sell = Trade(
        account="A",
        date=date(2024, 1, 1),
        ticker="TSLA",
        action="Sell",
        quantity=1.0,
        proceeds=200.0,
        cost_basis=500.0,
        option_details=OptionDetails(strike=250.0, expiry=date(2024, 12, 20), call_put="C"),
    )
    buy = Trade(
        account="B",
        date=date(2024, 1, 10),
        ticker="TSLA",
        action="Buy",
        quantity=1.0,
        cost_basis=600.0,
        option_details=OptionDetails(strike=250.0, expiry=date(2025, 3, 21), call_put="C"),
    )
    assert get_match_confidence(sell, buy, {}) == "Probable"


def test_stock_loss_buy_call_probable():
    """Sold stock at loss, bought call option on same stock."""
    sell = Trade(
        account="A",
        date=date(2024, 1, 1),
        ticker="TSLA",
        action="Sell",
        quantity=10.0,
        proceeds=2000.0,
        cost_basis=3000.0,
    )
    buy = Trade(
        account="B",
        date=date(2024, 1, 10),
        ticker="TSLA",
        action="Buy",
        quantity=1.0,
        cost_basis=500.0,
        option_details=OptionDetails(strike=250.0, expiry=date(2024, 12, 20), call_put="C"),
    )
    assert get_match_confidence(sell, buy, {}) == "Probable"


def test_stock_loss_buy_put_no_match():
    """Sold stock at loss, bought put option — not a wash sale trigger."""
    sell = Trade(
        account="A",
        date=date(2024, 1, 1),
        ticker="TSLA",
        action="Sell",
        quantity=10.0,
        proceeds=2000.0,
        cost_basis=3000.0,
    )
    buy = Trade(
        account="B",
        date=date(2024, 1, 10),
        ticker="TSLA",
        action="Buy",
        quantity=1.0,
        cost_basis=300.0,
        option_details=OptionDetails(strike=200.0, expiry=date(2024, 12, 20), call_put="P"),
    )
    assert get_match_confidence(sell, buy, {}) is None


def test_stock_loss_sold_put_unclear():
    """Sold stock at loss, sold put option on same stock — gray area."""
    sell = Trade(
        account="A",
        date=date(2024, 1, 1),
        ticker="TSLA",
        action="Sell",
        quantity=10.0,
        proceeds=2000.0,
        cost_basis=3000.0,
    )
    sold_put = Trade(
        account="A",
        date=date(2024, 1, 10),
        ticker="TSLA",
        action="Sell",
        quantity=1.0,
        proceeds=300.0,
        option_details=OptionDetails(strike=200.0, expiry=date(2024, 12, 20), call_put="P"),
    )
    assert get_match_confidence(sell, sold_put, {}) == "Unclear"


def test_option_loss_buy_stock_probable():
    """Sold option at loss, bought underlying stock."""
    sell = Trade(
        account="A",
        date=date(2024, 1, 1),
        ticker="TSLA",
        action="Sell",
        quantity=1.0,
        proceeds=100.0,
        cost_basis=500.0,
        option_details=OptionDetails(strike=250.0, expiry=date(2024, 12, 20), call_put="C"),
    )
    buy = Trade(
        account="B",
        date=date(2024, 1, 10),
        ticker="TSLA",
        action="Buy",
        quantity=10.0,
        cost_basis=2500.0,
    )
    assert get_match_confidence(sell, buy, {}) == "Probable"


# --- ETF confidence tests (Task 9) ---

ETF_PAIRS = {
    "sp500": ["SPY", "VOO", "IVV", "SPLG"],
    "nasdaq100": ["QQQ", "QQQM"],
}


def test_etf_same_ticker_confirmed():
    """Sold ETF at loss, bought same ETF ticker."""
    sell = Trade(
        account="A",
        date=date(2024, 1, 1),
        ticker="SPY",
        action="Sell",
        quantity=10.0,
        proceeds=4000.0,
        cost_basis=5000.0,
    )
    buy = Trade(
        account="B",
        date=date(2024, 1, 10),
        ticker="SPY",
        action="Buy",
        quantity=10.0,
        cost_basis=4500.0,
    )
    assert get_match_confidence(sell, buy, ETF_PAIRS) == "Confirmed"


def test_etf_substantially_identical_unclear():
    """Sold ETF at loss, bought substantially-identical ETF."""
    sell = Trade(
        account="A",
        date=date(2024, 1, 1),
        ticker="SPY",
        action="Sell",
        quantity=10.0,
        proceeds=4000.0,
        cost_basis=5000.0,
    )
    buy = Trade(
        account="B",
        date=date(2024, 1, 10),
        ticker="VOO",
        action="Buy",
        quantity=10.0,
        cost_basis=4500.0,
    )
    assert get_match_confidence(sell, buy, ETF_PAIRS) == "Unclear"


def test_etf_different_group_no_match():
    """SPY and QQQ are in different groups — no match."""
    sell = Trade(
        account="A",
        date=date(2024, 1, 1),
        ticker="SPY",
        action="Sell",
        quantity=10.0,
        proceeds=4000.0,
        cost_basis=5000.0,
    )
    buy = Trade(
        account="B",
        date=date(2024, 1, 10),
        ticker="QQQ",
        action="Buy",
        quantity=10.0,
        cost_basis=4500.0,
    )
    assert get_match_confidence(sell, buy, ETF_PAIRS) is None


def test_etf_constituent_stock_no_match():
    """Sold ETF at loss, bought constituent stock — not a wash sale."""
    sell = Trade(
        account="A",
        date=date(2024, 1, 1),
        ticker="SPY",
        action="Sell",
        quantity=10.0,
        proceeds=4000.0,
        cost_basis=5000.0,
    )
    buy = Trade(
        account="B",
        date=date(2024, 1, 10),
        ticker="AAPL",
        action="Buy",
        quantity=10.0,
        cost_basis=1500.0,
    )
    assert get_match_confidence(sell, buy, ETF_PAIRS) is None
