from datetime import date

from net_alpha.cli.simulate import _compute_safe_date, _find_lookback_triggers
from net_alpha.models.domain import Trade


def test_find_lookback_triggers():
    today = date(2024, 11, 15)
    trades = [
        Trade(
            account="Robinhood", date=date(2024, 11, 3), ticker="TSLA", action="Buy", quantity=15.0, cost_basis=3750.0
        ),
        Trade(account="Schwab", date=date(2024, 10, 16), ticker="TSLA", action="Buy", quantity=5.0, cost_basis=1000.0),
        Trade(
            account="Schwab", date=date(2024, 9, 1), ticker="TSLA", action="Buy", quantity=10.0, cost_basis=2000.0
        ),  # > 30 days ago
    ]
    triggers = _find_lookback_triggers("TSLA", today, trades, {})
    assert len(triggers) == 2  # Only buys within 30 days


def test_compute_safe_date():
    buy_date = date(2024, 11, 3)
    safe = _compute_safe_date([buy_date])
    assert safe == date(2024, 12, 3)  # 30 days after latest buy


def test_compute_safe_date_multiple_buys():
    dates = [date(2024, 11, 3), date(2024, 11, 10)]
    safe = _compute_safe_date(dates)
    assert safe == date(2024, 12, 10)  # 30 days after latest
