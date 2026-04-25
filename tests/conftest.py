from datetime import date
from uuid import uuid4

import factory

from net_alpha.models.domain import Lot, OptionDetails, Trade


class TradeFactory(factory.Factory):
    class Meta:
        model = Trade

    id = factory.LazyFunction(lambda: str(uuid4()))
    account = "Schwab"
    date = factory.LazyFunction(lambda: date(2024, 10, 15))
    ticker = "TSLA"
    action = "Buy"
    quantity = 10.0
    proceeds = None
    cost_basis = 2400.0
    basis_unknown = False
    option_details = None


class LossSaleFactory(TradeFactory):
    action = "Sell"
    proceeds = 2400.0
    cost_basis = 3600.0


class OptionTradeFactory(TradeFactory):
    option_details = factory.LazyFunction(lambda: OptionDetails(strike=250.0, expiry=date(2024, 12, 20), call_put="C"))


class LotFactory(factory.Factory):
    class Meta:
        model = Lot

    id = factory.LazyFunction(lambda: str(uuid4()))
    trade_id = factory.LazyFunction(lambda: str(uuid4()))
    account = "Schwab"
    date = factory.LazyFunction(lambda: date(2024, 10, 15))
    ticker = "TSLA"
    quantity = 10.0
    cost_basis = 2400.0
    adjusted_basis = 2400.0


