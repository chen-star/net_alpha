from __future__ import annotations

from datetime import date

from net_alpha.models.domain import Trade
from net_alpha.web.format import display_action


def _t(action="Buy", basis_source="broker_csv"):
    return Trade(
        account="Schwab/Tax", date=date(2026, 1, 15), ticker="AAPL",
        action=action, quantity=10, basis_source=basis_source,
    )


def test_display_action_transfer_in():
    assert display_action(_t(action="Buy", basis_source="transfer_in")) == "Transfer In"


def test_display_action_transfer_out():
    assert display_action(_t(action="Sell", basis_source="transfer_out")) == "Transfer Out"


def test_display_action_regular_buy():
    assert display_action(_t(action="Buy", basis_source="broker_csv")) == "Buy"


def test_display_action_regular_sell():
    assert display_action(_t(action="Sell", basis_source="broker_csv")) == "Sell"


def test_display_action_user_manual_buy():
    assert display_action(_t(action="Buy", basis_source="user")) == "Buy"
