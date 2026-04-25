from datetime import date

from net_alpha.models.domain import OptionDetails, Trade


def test_trade_account_uses_broker_label_format():
    t = Trade(
        account="schwab/personal",
        date=date(2024, 1, 1),
        ticker="TSLA",
        action="Buy",
        quantity=10,
        proceeds=None,
        cost_basis=2000.0,
    )
    assert "/" in t.account


def test_trade_compute_natural_key_is_deterministic():
    t1 = Trade(
        account="schwab/personal", date=date(2024, 1, 1), ticker="TSLA", action="Buy", quantity=10, cost_basis=2000.0
    )
    t2 = Trade(
        account="schwab/personal", date=date(2024, 1, 1), ticker="TSLA", action="Buy", quantity=10, cost_basis=2000.0
    )
    assert t1.compute_natural_key() == t2.compute_natural_key()


def test_natural_key_differs_when_quantity_differs():
    a = Trade(
        account="schwab/personal", date=date(2024, 1, 1), ticker="TSLA", action="Buy", quantity=10, cost_basis=2000.0
    )
    b = Trade(
        account="schwab/personal", date=date(2024, 1, 1), ticker="TSLA", action="Buy", quantity=11, cost_basis=2000.0
    )
    assert a.compute_natural_key() != b.compute_natural_key()


def test_natural_key_differs_across_accounts():
    a = Trade(
        account="schwab/personal", date=date(2024, 1, 1), ticker="TSLA", action="Buy", quantity=10, cost_basis=2000.0
    )
    b = Trade(account="schwab/roth", date=date(2024, 1, 1), ticker="TSLA", action="Buy", quantity=10, cost_basis=2000.0)
    assert a.compute_natural_key() != b.compute_natural_key()


def test_natural_key_includes_option_details():
    base_kwargs = dict(
        account="schwab/personal", date=date(2024, 1, 1), ticker="TSLA", action="Buy", quantity=1, cost_basis=500.0
    )
    a = Trade(**base_kwargs, option_details=OptionDetails(strike=200.0, expiry=date(2024, 6, 21), call_put="C"))
    b = Trade(**base_kwargs, option_details=OptionDetails(strike=210.0, expiry=date(2024, 6, 21), call_put="C"))
    assert a.compute_natural_key() != b.compute_natural_key()
