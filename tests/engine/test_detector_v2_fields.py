from datetime import date

from net_alpha.engine.detector import detect_wash_sales
from net_alpha.models.domain import Trade


def test_violations_carry_account_displays_and_dates():
    trades = [
        Trade(
            account="schwab/personal",
            date=date(2024, 3, 1),
            ticker="TSLA",
            action="Sell",
            quantity=10,
            proceeds=1500.0,
            cost_basis=2000.0,
        ),
        Trade(
            account="schwab/roth", date=date(2024, 3, 10), ticker="TSLA", action="Buy", quantity=10, cost_basis=1700.0
        ),
    ]
    result = detect_wash_sales(trades, etf_pairs={})
    assert len(result.violations) == 1
    v = result.violations[0]
    assert v.loss_account == "schwab/personal"
    assert v.buy_account == "schwab/roth"
    assert v.loss_sale_date == date(2024, 3, 1)
    assert v.triggering_buy_date == date(2024, 3, 10)
