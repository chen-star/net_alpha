from datetime import date

import pytest

from net_alpha.audit.brokers.base import BrokerGLProvider, BrokerLot


def test_broker_lot_validates():
    lot = BrokerLot(
        symbol="AAPL",
        account_id=1,
        acquired=date(2026, 1, 1),
        closed=date(2026, 4, 1),
        qty=10.0,
        cost_basis=1000.0,
        proceeds=1500.0,
        wash_disallowed=None,
        source_label="Schwab Realized G/L",
    )
    assert lot.symbol == "AAPL"


def test_abc_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BrokerGLProvider()


def test_abc_subclass_must_implement_both_methods():
    class Half(BrokerGLProvider):
        def supports(self, account_id):
            return True

    with pytest.raises(TypeError):
        Half()
