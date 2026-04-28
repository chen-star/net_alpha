from datetime import date
from decimal import Decimal

from net_alpha.portfolio.tax_planner import OffsetBudget, PlannedTrade


def test_offset_budget_constructs() -> None:
    b = OffsetBudget(
        year=2026,
        realized_losses_ytd=Decimal("-1000"),
        realized_gains_ytd=Decimal("500"),
        net_realized=Decimal("-500"),
        used_against_ordinary=Decimal("500"),
        carryforward_projection=Decimal("0"),
        planned_delta=Decimal("0"),
    )
    assert b.cap_against_ordinary == Decimal("3000")  # default


def test_planned_trade_constructs() -> None:
    pt = PlannedTrade(
        symbol="UUUU",
        account_id=1,
        action="Sell",
        qty=Decimal("100"),
        price=Decimal("4"),
        on=date(2026, 6, 1),
    )
    assert pt.action == "Sell"
