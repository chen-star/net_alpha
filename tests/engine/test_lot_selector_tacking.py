"""Lot selector honors IRC §1223(4) wash-sale tacking for ST/LT classification.

A replacement lot with ``tacked_acquired_date`` set to >365 days before the
sell date is long-term, even if the raw lot date is < 365 days back.
"""

from datetime import date
from decimal import Decimal

from net_alpha.engine.lot_selector import select_lots
from net_alpha.models.domain import Lot


def _lot(*, qty: float, basis: float, acquired: date, tacked: date | None = None):
    return Lot(
        id="lot-1",
        trade_id="t1",
        ticker="SPY",
        date=acquired,
        quantity=qty,
        cost_basis=basis,
        adjusted_basis=basis,
        account="default",
        tacked_acquired_date=tacked,
    )


def test_tacked_lot_classifies_as_long_term():
    """100-day raw hold, but tacked back to 800 days ago → LT."""
    lot = _lot(
        qty=10.0,
        basis=1000.0,
        acquired=date(2026, 1, 25),  # 100 days before sell
        tacked=date(2024, 3, 1),  # ~795 days before sell
    )
    result = select_lots(
        lots=[lot],
        qty=Decimal("10"),
        sell_price=Decimal("120"),
        sell_date=date(2026, 5, 5),
        strategy="FIFO",
        repo=None,
        etf_pairs={},
        brackets=None,
        carryforward=None,
    )
    pick = result.picks[0]
    assert pick.is_long_term is True
    assert pick.holding_period_days > 365
    # P&L bucketed as LT in the LotPickResult.
    assert result.lt_pnl == Decimal("200")
    assert result.st_pnl == Decimal("0")


def test_untacked_lot_classifies_as_short_term():
    """Same 100-day raw hold but no tacking → ST (sanity check baseline)."""
    lot = _lot(
        qty=10.0,
        basis=1000.0,
        acquired=date(2026, 1, 25),
        tacked=None,
    )
    result = select_lots(
        lots=[lot],
        qty=Decimal("10"),
        sell_price=Decimal("120"),
        sell_date=date(2026, 5, 5),
        strategy="FIFO",
        repo=None,
        etf_pairs={},
        brackets=None,
        carryforward=None,
    )
    pick = result.picks[0]
    assert pick.is_long_term is False
    assert pick.holding_period_days == 100
    assert result.st_pnl == Decimal("200")
    assert result.lt_pnl == Decimal("0")
