from datetime import date

from net_alpha.models.domain import OptionDetails, Trade


def test_trade_equity_loss():
    trade = Trade(
        account="Schwab",
        date=date(2024, 10, 15),
        ticker="TSLA",
        action="Sell",
        quantity=10.0,
        proceeds=2400.0,
        cost_basis=3600.0,
    )
    assert trade.is_sell() is True
    assert trade.is_buy() is False
    assert trade.is_option() is False
    assert trade.is_loss() is True
    assert trade.loss_amount() == 1200.0


def test_trade_equity_gain():
    trade = Trade(
        account="Schwab",
        date=date(2024, 10, 15),
        ticker="TSLA",
        action="Sell",
        quantity=10.0,
        proceeds=5000.0,
        cost_basis=3600.0,
    )
    assert trade.is_loss() is False
    assert trade.loss_amount() == 0.0


def test_trade_buy_is_never_loss():
    trade = Trade(
        account="Schwab",
        date=date(2024, 10, 15),
        ticker="TSLA",
        action="Buy",
        quantity=10.0,
        cost_basis=3600.0,
    )
    assert trade.is_loss() is False


def test_trade_basis_unknown_is_never_loss():
    trade = Trade(
        account="Schwab",
        date=date(2024, 10, 15),
        ticker="TSLA",
        action="Sell",
        quantity=10.0,
        proceeds=2400.0,
        basis_unknown=True,
    )
    assert trade.is_loss() is False
    assert trade.loss_amount() == 0.0


def test_trade_with_option_details():
    trade = Trade(
        account="Schwab",
        date=date(2024, 10, 15),
        ticker="TSLA",
        action="Buy",
        quantity=1.0,
        cost_basis=500.0,
        option_details=OptionDetails(
            strike=250.0,
            expiry=date(2024, 12, 20),
            call_put="C",
        ),
    )
    assert trade.is_option() is True
    assert trade.option_details.strike == 250.0
    assert trade.option_details.call_put == "C"


def test_trade_id_auto_generated():
    t1 = Trade(account="A", date=date(2024, 1, 1), ticker="X", action="Buy", quantity=1.0)
    t2 = Trade(account="A", date=date(2024, 1, 1), ticker="X", action="Buy", quantity=1.0)
    assert t1.id != t2.id
    assert len(t1.id) == 36  # UUID format
