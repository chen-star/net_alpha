# tests/portfolio/test_positions_density_extras.py
import datetime as dt
from datetime import date
from decimal import Decimal

import factory

from net_alpha.models.domain import Lot, Trade
from net_alpha.portfolio.positions import compute_open_positions
from net_alpha.pricing.provider import Quote


class _LotF(factory.Factory):
    class Meta:
        model = Lot

    id = factory.Sequence(lambda n: str(n + 1))
    trade_id = factory.Sequence(lambda n: f"t{n + 1}")
    account = "Schwab/Tax"
    ticker = "AAPL"
    quantity = 100.0
    cost_basis = 10000.0
    adjusted_basis = 10000.0
    date = date(2024, 1, 1)
    option_details = None


class _BuyF(factory.Factory):
    class Meta:
        model = Trade

    account = "Schwab/Tax"
    date = date(2024, 1, 1)
    ticker = "AAPL"
    action = "Buy"
    quantity = 100.0
    proceeds = None
    cost_basis = 10000.0


def test_position_row_carries_oldest_lot_age_days():
    """When a single open lot, days_held = today - lot.date."""
    lots = [_LotF(quantity=100.0, date=date(2024, 1, 1))]
    trades = [_BuyF(quantity=100.0, date=date(2024, 1, 1))]
    rows = compute_open_positions(
        trades=trades,
        lots=lots,
        prices={"AAPL": Quote(symbol="AAPL", price=Decimal("150"), as_of=dt.datetime(2026, 4, 27, tzinfo=dt.timezone.utc), source="test")},
        as_of=date(2026, 4, 27),
    )
    aapl = next(r for r in rows if r.symbol == "AAPL")
    assert aapl.days_held == (date(2026, 4, 27) - date(2024, 1, 1)).days


def test_position_row_carries_lt_st_split():
    """Open lots > 365 days = LT, otherwise ST. Split on a per-share basis."""
    lots = [
        _LotF(id="1", quantity=70.0, date=date(2024, 1, 1)),  # >365d on 2026-04-27 -> LT
        _LotF(id="2", quantity=30.0, date=date(2026, 1, 1)),  # <365d on 2026-04-27 -> ST
    ]
    trades = [
        _BuyF(quantity=70.0, date=date(2024, 1, 1)),
        _BuyF(quantity=30.0, date=date(2026, 1, 1)),
    ]
    rows = compute_open_positions(
        trades=trades,
        lots=lots,
        prices={"AAPL": Quote(symbol="AAPL", price=Decimal("150"), as_of=dt.datetime(2026, 4, 27, tzinfo=dt.timezone.utc), source="test")},
        as_of=date(2026, 4, 27),
    )
    aapl = next(r for r in rows if r.symbol == "AAPL")
    assert aapl.lt_qty == Decimal("70")
    assert aapl.st_qty == Decimal("30")
