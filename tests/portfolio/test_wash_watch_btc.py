"""Wash-watch panel must include short-option Buy-to-Close losses.

Regression for the C3-sibling bug: ``recent_loss_closes`` filtered on
``t.action.lower() != "sell"``, so closing a short option at a loss
(BTC) never surfaced on the panel. The user got no warning before
re-selling the same strike inside the §1091 30-day window.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from net_alpha.models.domain import OptionDetails, Trade
from net_alpha.portfolio.wash_watch import recent_loss_closes


def _sto(account: str, ticker: str, day: date, *, premium: float, qty: float = 1.0) -> Trade:
    return Trade(
        account=account,
        date=day,
        ticker=ticker,
        action="Sell",
        quantity=qty,
        proceeds=premium,
        cost_basis=None,
        basis_source="option_short_open",
        option_details=OptionDetails(strike=100.0, expiry=date(2026, 6, 19), call_put="P"),
    )


def _btc(account: str, ticker: str, day: date, *, paid: float, qty: float = 1.0) -> Trade:
    return Trade(
        account=account,
        date=day,
        ticker=ticker,
        action="Buy",
        quantity=qty,
        proceeds=None,
        cost_basis=paid,
        basis_source="option_short_close",
        option_details=OptionDetails(strike=100.0, expiry=date(2026, 6, 19), call_put="P"),
    )


def _repo(trades: list[Trade]) -> MagicMock:
    r = MagicMock()
    r.all_trades.return_value = trades
    return r


def test_btc_at_a_loss_appears_in_recent_loss_closes():
    """STO @ $50 then BTC @ $200 within window → -$150 loss surfaced."""
    today = date(2026, 5, 18)
    trades = [
        _sto("schwab/personal", "TSLA", date(2026, 4, 1), premium=50.0),
        _btc("schwab/personal", "TSLA", date(2026, 5, 10), paid=200.0),
    ]
    rows = recent_loss_closes(repo=_repo(trades), today=today, window_days=30)
    assert len(rows) == 1
    r = rows[0]
    assert r.symbol == "TSLA"
    assert r.close_date == date(2026, 5, 10)
    assert r.loss_amount == Decimal("150")


def test_btc_at_a_gain_does_not_appear():
    """STO @ $100 then BTC @ $20 → +$80 gain; not a loss-close."""
    today = date(2026, 5, 18)
    trades = [
        _sto("schwab/personal", "TSLA", date(2026, 4, 1), premium=100.0),
        _btc("schwab/personal", "TSLA", date(2026, 5, 10), paid=20.0),
    ]
    rows = recent_loss_closes(repo=_repo(trades), today=today, window_days=30)
    assert rows == []


def test_btc_outside_window_excluded():
    today = date(2026, 5, 18)
    trades = [
        _sto("schwab/personal", "TSLA", date(2026, 1, 5), premium=50.0),
        _btc("schwab/personal", "TSLA", date(2026, 3, 1), paid=200.0),  # 78 days ago
    ]
    rows = recent_loss_closes(repo=_repo(trades), today=today, window_days=30)
    assert rows == []
