import pytest

from net_alpha.brokers.schwab import SchwabParser


def _row(**kw):
    base = {
        "Date": "04/24/2026", "Action": "Buy", "Symbol": "SPIR",
        "Description": "SPIRE GLOBAL", "Quantity": "10", "Price": "$15.88",
        "Fees & Comm": "", "Amount": "-$158.80",
    }
    base.update(kw)
    return base


def test_buy_populates_negative_gross_cash_impact():
    trades = SchwabParser().parse([_row()], "Schwab/x")
    assert len(trades) == 1
    assert trades[0].gross_cash_impact == -158.80


def test_sell_populates_positive_gross_cash_impact():
    rows = [_row(Action="Sell", Amount="$824.96")]
    trades = SchwabParser().parse(rows, "Schwab/x")
    assert trades[0].gross_cash_impact == 824.96


def test_put_assignment_buy_gross_is_strike_not_basis_adjusted():
    """Sell-to-Open net amount of $87.34, then Assigned Buy at $3 strike for 100 shares.
    cost_basis becomes 212.66 (strike*qty - net_premium); gross_cash_impact stays -300.
    """
    rows = [
        {
            "Date": "03/19/2026", "Action": "Sell to Open",
            "Symbol": "RR 04/17/2026 3.00 P",
            "Description": "PUT RICHTECH ROBOTICS IN$3 EXP 04/17/26",
            "Quantity": "1", "Price": "$0.88", "Fees & Comm": "$0.66",
            "Amount": "$87.34",
        },
        {
            "Date": "04/20/2026 as of 04/17/2026", "Action": "Assigned",
            "Symbol": "RR 04/17/2026 3.00 P",
            "Description": "PUT RICHTECH ROBOTICS IN$3 EXP 04/17/26",
            "Quantity": "1", "Price": "", "Fees & Comm": "", "Amount": "",
        },
        {
            "Date": "04/20/2026 as of 04/17/2026", "Action": "Buy",
            "Symbol": "RR", "Description": "RICHTECH ROBOTICS",
            "Quantity": "100", "Price": "$3.00", "Fees & Comm": "",
            "Amount": "-$300.00",
        },
    ]
    trades = SchwabParser().parse(rows, "Schwab/x")
    buys = [t for t in trades if t.action == "Buy" and not t.is_option()]
    assert len(buys) == 1
    assert buys[0].cost_basis == pytest.approx(212.66, abs=0.01)  # adjusted for premium offset
    assert buys[0].gross_cash_impact == -300.0  # actual cash debit
