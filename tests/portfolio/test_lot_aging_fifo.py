"""``top_lots_crossing_ltcg`` must skip lots consumed by prior sells.

Regression for the C4 bug: the function iterated raw ``Lot`` rows and
only filtered ``lot.quantity <= 0``. But ``lot.quantity`` is the
*original* buy size — FIFO consumption against subsequent sells happens
via ``consume_lots_fifo``, not by mutating the row. So a 10-share buy
that was later fully sold still surfaced as "crossing LTCG soon."
"""

from __future__ import annotations

import datetime as dt

from net_alpha.models.domain import Lot, Trade
from net_alpha.portfolio.lot_aging import top_lots_crossing_ltcg


def _lot(symbol: str, account: str, days_old: int, qty: float = 10.0) -> Lot:
    today = dt.date.today()
    return Lot(
        id=f"l_{symbol}",
        trade_id=f"t_{symbol}",
        account=account,
        date=today - dt.timedelta(days=days_old),
        ticker=symbol,
        quantity=qty,
        cost_basis=1000.0,
        adjusted_basis=1000.0,
        option_details=None,
    )


def _sell(symbol: str, account: str, days_ago: int, qty: float) -> Trade:
    today = dt.date.today()
    return Trade(
        account=account,
        date=today - dt.timedelta(days=days_ago),
        ticker=symbol,
        action="Sell",
        quantity=qty,
        proceeds=1500.0,
        cost_basis=1000.0,
    )


def test_fully_sold_lot_excluded_when_trades_provided():
    """10-share buy 300 days ago, 10-share sell 5 days ago → no open position
    even though the lot.quantity row still reads 10."""
    lot = _lot("AAPL", "schwab/personal", days_old=300, qty=10.0)
    sell = _sell("AAPL", "schwab/personal", days_ago=5, qty=10.0)

    out = top_lots_crossing_ltcg(lots=[lot], trades=[sell], horizon_days=90, top_n=5)
    assert out == []


def test_partially_sold_lot_still_appears_with_remaining_qty():
    """10-share buy 300 days ago, 4-share sell → 6 shares remain open."""
    lot = _lot("AAPL", "schwab/personal", days_old=300, qty=10.0)
    sell = _sell("AAPL", "schwab/personal", days_ago=5, qty=4.0)

    out = top_lots_crossing_ltcg(lots=[lot], trades=[sell], horizon_days=90, top_n=5)
    assert len(out) == 1
    assert out[0].symbol == "AAPL"
    # Remaining qty after FIFO consumption.
    assert out[0].qty == 6.0


def test_legacy_no_trades_arg_still_works():
    """Existing callers that don't pass trades get current behavior so the
    public API stays back-compatible until they migrate."""
    lot = _lot("AAPL", "schwab/personal", days_old=300, qty=10.0)
    out = top_lots_crossing_ltcg(lots=[lot], horizon_days=90, top_n=5)
    assert len(out) == 1
    assert out[0].symbol == "AAPL"
