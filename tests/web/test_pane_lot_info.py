"""Unit tests for the _pane_lot_info helper's unrealized P&L formula.

adjusted_basis on a Lot is a total-dollar amount for the lot, not a
per-share price. The correct formula is:

    unrealized = price * quantity - adjusted_basis

These tests lock in that formula using a known fixture (100 shares,
$15000 total basis) and verify gain, loss, and None (no price) cases.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from net_alpha.models.domain import Lot
from net_alpha.web.routes.positions import _pane_lot_info


def _make_lot(qty: float, adjusted_basis: float) -> Lot:
    """Construct a minimal open equity Lot for testing."""
    return Lot(
        trade_id="t1",
        account="Schwab/Test",
        date=dt.date(2024, 1, 1),
        ticker="TEST",
        quantity=qty,
        cost_basis=adjusted_basis,
        adjusted_basis=adjusted_basis,
    )


TODAY = dt.date(2025, 6, 1)  # deterministic; lot is >365 days old (LT)


def test_unrealized_gain_case() -> None:
    """100 shares, $15000 basis, price $160 → unrealized = +$1000."""
    lot = _make_lot(qty=100.0, adjusted_basis=15000.0)
    result = _pane_lot_info(open_equity_lots=[lot], last_price=160.0, today=TODAY)
    assert result["lots"][0]["unrealized"] == Decimal("1000")


def test_unrealized_loss_case() -> None:
    """100 shares, $15000 basis, price $140 → unrealized = -$1000."""
    lot = _make_lot(qty=100.0, adjusted_basis=15000.0)
    result = _pane_lot_info(open_equity_lots=[lot], last_price=140.0, today=TODAY)
    assert result["lots"][0]["unrealized"] == Decimal("-1000")


def test_unrealized_none_when_no_price() -> None:
    """When last_price is None the unrealized field must be None."""
    lot = _make_lot(qty=100.0, adjusted_basis=15000.0)
    result = _pane_lot_info(open_equity_lots=[lot], last_price=None, today=TODAY)
    assert result["lots"][0]["unrealized"] is None
