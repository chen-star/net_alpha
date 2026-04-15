from datetime import date
from uuid import uuid4

import factory

from net_alpha.models.domain import Lot, OpenLot, OptionDetails, RealizedPair, Trade


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


class OpenLotFactory(factory.Factory):
    class Meta:
        model = OpenLot

    ticker = "AAPL"
    account = "Schwab"
    quantity = 50.0
    adjusted_basis_per_share = 145.0
    purchase_date = factory.LazyFunction(lambda: date(2025, 6, 1))
    days_held = 315
    days_to_long_term = 50
    basis_unknown = False
    is_option = False


class RealizedPairFactory(factory.Factory):
    class Meta:
        model = RealizedPair

    sell_trade_id = factory.LazyFunction(lambda: str(uuid4()))
    buy_lot_date = factory.LazyFunction(lambda: date(2025, 1, 15))
    buy_lot_account = "Schwab"
    quantity = 10.0
    proceeds = 1800.0
    basis = 1500.0
    basis_unknown = False
    is_long_term = False
