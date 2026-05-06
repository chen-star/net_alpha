from datetime import date
from decimal import Decimal

import pytest

from net_alpha.engine.lot_selector import (
    InsufficientLotsError,
    LotPick,  # noqa: F401 — re-export sanity check
    LotPickResult,
    select_lots,
)


def _lot(id: int, qty: float, basis: float, acquired: date):
    """Build a minimal Lot domain object for tests."""
    from net_alpha.models.domain import Lot

    return Lot(
        id=str(id),
        trade_id=f"t{id}",
        ticker="SPY",
        date=acquired,
        quantity=qty,
        cost_basis=basis,
        adjusted_basis=basis,
        account="default",
    )


def test_insufficient_lots_raises():
    lots = [_lot(1, 10, 1000, date(2024, 1, 1))]
    with pytest.raises(InsufficientLotsError):
        select_lots(
            lots=lots,
            qty=Decimal("100"),
            sell_price=Decimal("110"),
            sell_date=date(2026, 5, 5),
            strategy="FIFO",
            repo=None,
            etf_pairs={},
            brackets=None,
            carryforward=None,
        )


def test_lot_pick_result_has_required_fields():
    lots = [_lot(1, 100, 50.0, date(2024, 1, 1))]
    result = select_lots(
        lots=lots,
        qty=Decimal("50"),
        sell_price=Decimal("100"),
        sell_date=date(2026, 5, 5),
        strategy="FIFO",
        repo=None,
        etf_pairs={},
        brackets=None,
        carryforward=None,
    )
    assert isinstance(result, LotPickResult)
    assert result.strategy == "FIFO"
    assert len(result.picks) == 1
    assert result.picks[0].qty_consumed == Decimal("50")
    assert result.pre_tax_pnl == Decimal("2500")  # (100 - 50) * 50
    assert result.has_wash_sale_risk is False
    assert result.wash_sale_disallowed == Decimal("0")
