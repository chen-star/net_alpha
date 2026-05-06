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


def _make_lots():
    """3 same-size lots with distinct dates and basis-per-share."""
    return [
        _lot(1, 100, 8000.0, date(2023, 1, 15)),  # oldest, low basis ($80/sh)
        _lot(2, 100, 12000.0, date(2024, 6, 1)),  # mid, high basis ($120/sh)
        _lot(3, 100, 10000.0, date(2025, 3, 1)),  # newest, mid basis ($100/sh)
    ]


def _strategy_pick_ids(strategy: str) -> list[str]:
    lots = _make_lots()
    result = select_lots(
        lots=lots,
        qty=Decimal("150"),
        sell_price=Decimal("110"),
        sell_date=date(2026, 5, 5),
        strategy=strategy,
        repo=None,
        etf_pairs={},
        brackets=None,
        carryforward=None,
    )
    return [p.lot_id for p in result.picks]


def test_fifo_consumes_oldest_first():
    assert _strategy_pick_ids("FIFO") == ["1", "2"]


def test_lifo_consumes_newest_first():
    assert _strategy_pick_ids("LIFO") == ["3", "2"]


def test_hifo_consumes_highest_basis_first():
    assert _strategy_pick_ids("HIFO") == ["2", "3"]


def test_hifo_sorts_on_basis_per_share_not_total_basis():
    """A small lot with high $/share should win over a large lot with low $/share,
    even though the large lot has higher TOTAL basis. This is the correctness fix
    from Task 11 review."""
    lots = [
        _lot(1, 1000, 50000.0, date(2024, 1, 1)),  # 1000 sh @ $50/sh, total $50K
        _lot(2, 10, 2000.0, date(2024, 1, 2)),  # 10 sh @ $200/sh, total $2K
    ]
    result = select_lots(
        lots=lots,
        qty=Decimal("10"),
        sell_price=Decimal("110"),
        sell_date=date(2026, 5, 5),
        strategy="HIFO",
        repo=None,
        etf_pairs={},
        brackets=None,
        carryforward=None,
    )
    # HIFO should pick lot 2 first (higher per-share basis).
    assert [p.lot_id for p in result.picks] == ["2"]


def test_hifo_tiebreak_deterministic():
    """Two lots with identical basis-per-share → tiebreak by lot_id ascending."""
    lots = [
        _lot(2, 100, 10000.0, date(2024, 1, 1)),  # $100/sh
        _lot(1, 100, 10000.0, date(2025, 1, 1)),  # $100/sh — same per-share
    ]
    result = select_lots(
        lots=lots,
        qty=Decimal("100"),
        sell_price=Decimal("110"),
        sell_date=date(2026, 5, 5),
        strategy="HIFO",
        repo=None,
        etf_pairs={},
        brackets=None,
        carryforward=None,
    )
    # Tiebreak by lot_id ascending: "1" wins.
    assert result.picks[0].lot_id == "1"


def test_fifo_tiebreak_by_lot_id_when_same_date():
    lots = [
        _lot(2, 50, 5000.0, date(2024, 1, 1)),
        _lot(1, 50, 5000.0, date(2024, 1, 1)),
    ]
    result = select_lots(
        lots=lots,
        qty=Decimal("50"),
        sell_price=Decimal("110"),
        sell_date=date(2026, 5, 5),
        strategy="FIFO",
        repo=None,
        etf_pairs={},
        brackets=None,
        carryforward=None,
    )
    assert result.picks[0].lot_id == "1"
