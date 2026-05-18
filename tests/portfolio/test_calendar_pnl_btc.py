"""Calendar P&L must include short-option Buy-to-Close trades.

Regression for the C3 bug: ``monthly_realized_pl`` gated on
``t.action.lower() != "sell"``, so closing a short option (BTC) was
silently dropped from the monthly bar even though it is a realized
event. The heatmap then diverged from the headline Realized P&L KPI
on the same page.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from net_alpha.models.domain import OptionDetails, Trade
from net_alpha.portfolio.calendar_pnl import monthly_realized_pl


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
        option_details=OptionDetails(strike=100.0, expiry=date(2024, 12, 20), call_put="P"),
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
        option_details=OptionDetails(strike=100.0, expiry=date(2024, 12, 20), call_put="P"),
    )


def test_monthly_pl_includes_btc_at_a_profit():
    """STO June @ $100 premium, BTC July @ $30 to close → +$70 in July."""
    trades = [
        _sto("schwab/personal", "TSLA", date(2024, 6, 10), premium=100.0),
        _btc("schwab/personal", "TSLA", date(2024, 7, 5), paid=30.0),
    ]
    rows = monthly_realized_pl(trades=trades, year=2024, ticker=None)
    # July (index 6) should reflect the +$70 realized at close.
    july = next(r for r in rows if r.month == 7)
    assert july.net_pl == Decimal("70")
    assert july.gross_gain == Decimal("70")
    assert july.trade_count == 1


def test_monthly_pl_includes_btc_at_a_loss():
    """STO @ $50, BTC @ $80 → -$30 loss at the BTC date."""
    trades = [
        _sto("schwab/personal", "TSLA", date(2024, 5, 1), premium=50.0),
        _btc("schwab/personal", "TSLA", date(2024, 8, 2), paid=80.0),
    ]
    rows = monthly_realized_pl(trades=trades, year=2024, ticker=None)
    aug = next(r for r in rows if r.month == 8)
    assert aug.net_pl == Decimal("-30")
    assert aug.gross_loss == Decimal("30")


def test_monthly_pl_ignores_sto_open():
    """STO alone (no closing BTC) realizes nothing — premium is unrealized."""
    trades = [_sto("schwab/personal", "TSLA", date(2024, 3, 1), premium=120.0)]
    rows = monthly_realized_pl(trades=trades, year=2024, ticker=None)
    assert all(r.net_pl == Decimal("0") for r in rows)
