from datetime import date

from net_alpha.cli.check import _build_summary, _filter_violations_by_year
from net_alpha.models.domain import Trade, WashSaleViolation


def test_build_summary():
    violations = [
        WashSaleViolation(
            loss_trade_id="t1", replacement_trade_id="t2",
            confidence="Confirmed", disallowed_loss=1200.0, matched_quantity=10.0,
        ),
        WashSaleViolation(
            loss_trade_id="t3", replacement_trade_id="t4",
            confidence="Probable", disallowed_loss=500.0, matched_quantity=5.0,
        ),
        WashSaleViolation(
            loss_trade_id="t5", replacement_trade_id="t6",
            confidence="Confirmed", disallowed_loss=800.0, matched_quantity=8.0,
        ),
    ]
    summary = _build_summary(violations)
    assert summary["Confirmed"]["count"] == 2
    assert summary["Confirmed"]["total"] == 2000.0
    assert summary["Probable"]["count"] == 1
    assert summary["Probable"]["total"] == 500.0
    assert summary["Unclear"]["count"] == 0


def test_filter_violations_by_year():
    trades = {
        "t1": Trade(account="A", date=date(2024, 10, 15), ticker="TSLA", action="Sell", quantity=10.0),
        "t2": Trade(account="B", date=date(2025, 1, 5), ticker="TSLA", action="Sell", quantity=5.0),
    }
    violations = [
        WashSaleViolation(
            loss_trade_id="t1", replacement_trade_id="x",
            confidence="Confirmed", disallowed_loss=100.0, matched_quantity=1.0,
        ),
        WashSaleViolation(
            loss_trade_id="t2", replacement_trade_id="y",
            confidence="Confirmed", disallowed_loss=200.0, matched_quantity=2.0,
        ),
    ]

    filtered = _filter_violations_by_year(violations, trades, 2024)
    assert len(filtered) == 1
    assert filtered[0].loss_trade_id == "t1"
