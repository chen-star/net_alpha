# tests/portfolio/test_positions_premium.py
import datetime as dt
from datetime import date
from decimal import Decimal

from net_alpha.models.domain import Lot, OptionDetails, Trade
from net_alpha.portfolio.positions import compute_open_positions
from net_alpha.pricing.provider import Quote


def test_premium_received_for_closed_csp():
    """Sell-to-open then buy-to-close a put — net premium = STO - BTC."""
    csp_open = Trade(
        account="Schwab/Tax",
        date=date(2026, 1, 1),
        ticker="AAPL",
        action="Sell to Open",
        quantity=1.0,
        proceeds=200.0,
        cost_basis=None,
        option_details=OptionDetails(strike=140.0, expiry=date(2026, 4, 17), call_put="P"),
    )
    csp_close = Trade(
        account="Schwab/Tax",
        date=date(2026, 3, 1),
        ticker="AAPL",
        action="Buy to Close",
        quantity=1.0,
        proceeds=None,
        cost_basis=50.0,
        option_details=OptionDetails(strike=140.0, expiry=date(2026, 4, 17), call_put="P"),
    )
    # Plus an open equity lot so AAPL appears as a position.
    eq_lot = Lot(
        id="1", trade_id="t-eq", account="Schwab/Tax", ticker="AAPL",
        quantity=100.0, cost_basis=10000.0, adjusted_basis=10000.0,
        date=date(2024, 1, 1),
    )
    eq_buy = Trade(
        account="Schwab/Tax", date=date(2024, 1, 1), ticker="AAPL",
        action="Buy", quantity=100.0, proceeds=None, cost_basis=10000.0,
    )

    _as_of_dt = dt.datetime(2026, 4, 27, tzinfo=dt.UTC)
    rows = compute_open_positions(
        trades=[eq_buy, csp_open, csp_close],
        lots=[eq_lot],
        prices={"AAPL": Quote(symbol="AAPL", price=Decimal("150"), as_of=_as_of_dt, source="test")},
        as_of=date(2026, 4, 27),
    )
    aapl = next(r for r in rows if r.symbol == "AAPL")
    assert aapl.premium_received == Decimal("150")  # 200 - 50


def test_premium_received_zero_when_no_options():
    eq_lot = Lot(
        id="1", trade_id="t-eq", account="Schwab/Tax", ticker="AAPL",
        quantity=100.0, cost_basis=10000.0, adjusted_basis=10000.0,
        date=date(2024, 1, 1),
    )
    eq_buy = Trade(
        account="Schwab/Tax", date=date(2024, 1, 1), ticker="AAPL",
        action="Buy", quantity=100.0, proceeds=None, cost_basis=10000.0,
    )
    _as_of_dt = dt.datetime(2026, 4, 27, tzinfo=dt.UTC)
    rows = compute_open_positions(
        trades=[eq_buy],
        lots=[eq_lot],
        prices={"AAPL": Quote(symbol="AAPL", price=Decimal("150"), as_of=_as_of_dt, source="test")},
        as_of=date(2026, 4, 27),
    )
    aapl = next(r for r in rows if r.symbol == "AAPL")
    assert aapl.premium_received == Decimal("0")
