from datetime import date

from net_alpha.engine.detector import detect_in_window, detect_wash_sales
from net_alpha.models.domain import Trade


def _t(d, ticker, action, qty, proceeds=None, basis=None, account="schwab/personal"):
    return Trade(
        account=account, date=d, ticker=ticker, action=action, quantity=qty, proceeds=proceeds, cost_basis=basis
    )


def test_detect_in_window_subsets_full_scan():
    trades = [
        _t(date(2024, 1, 1), "TSLA", "Buy", 10, basis=2000),
        _t(date(2024, 6, 1), "TSLA", "Sell", 10, proceeds=1500, basis=2000),  # loss
        _t(date(2024, 6, 5), "TSLA", "Buy", 10, basis=1700),  # triggers
        _t(date(2024, 12, 1), "AAPL", "Sell", 10, proceeds=500, basis=1000),  # unrelated loss
    ]
    full = detect_wash_sales(trades, etf_pairs={})
    windowed = detect_in_window(trades, date(2024, 5, 1), date(2024, 7, 1), etf_pairs={})

    full_in_window = [
        v for v in full.violations if v.loss_sale_date and date(2024, 5, 1) <= v.loss_sale_date <= date(2024, 7, 1)
    ]
    assert len(windowed.violations) == len(full_in_window)
    assert windowed.violations[0].confidence == "Confirmed"


def test_detect_in_window_excludes_loss_outside_window():
    trades = [
        _t(date(2024, 1, 1), "TSLA", "Buy", 10, basis=2000),
        _t(date(2024, 6, 1), "TSLA", "Sell", 10, proceeds=1500, basis=2000),
        _t(date(2024, 6, 5), "TSLA", "Buy", 10, basis=1700),
    ]
    windowed = detect_in_window(trades, date(2024, 7, 2), date(2024, 8, 1), etf_pairs={})
    assert windowed.violations == []
