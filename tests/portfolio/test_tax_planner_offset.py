from datetime import date
from decimal import Decimal

from net_alpha.models.domain import Trade
from net_alpha.portfolio.tax_planner import OffsetBudget, PlannedTrade, compute_offset_budget


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


def test_compute_offset_budget_no_trades(repo) -> None:
    b = compute_offset_budget(repo=repo, year=2026)
    assert b.realized_losses_ytd == Decimal("0")
    assert b.realized_gains_ytd == Decimal("0")
    assert b.net_realized == Decimal("0")
    assert b.used_against_ordinary == Decimal("0")
    assert b.carryforward_projection == Decimal("0")


def test_compute_offset_budget_aggregates_realized_in_year(
    repo, schwab_account, seed_import,
) -> None:
    buys = [
        Trade(account=schwab_account.display(), date=date(2026, 1, 5),
              ticker="UUUU", action="Buy", quantity=Decimal("1"),
              proceeds=Decimal("0"), cost_basis=Decimal("100")),
        Trade(account=schwab_account.display(), date=date(2026, 1, 5),
              ticker="AAPL", action="Buy", quantity=Decimal("1"),
              proceeds=Decimal("0"), cost_basis=Decimal("100")),
    ]
    sells = [
        Trade(account=schwab_account.display(), date=date(2026, 3, 1),
              ticker="UUUU", action="Sell", quantity=Decimal("1"),
              proceeds=Decimal("80"), cost_basis=Decimal("100")),
        Trade(account=schwab_account.display(), date=date(2026, 4, 1),
              ticker="AAPL", action="Sell", quantity=Decimal("1"),
              proceeds=Decimal("130"), cost_basis=Decimal("100")),
    ]
    seed_import(repo, schwab_account, buys + sells)
    b = compute_offset_budget(repo=repo, year=2026)
    assert b.realized_losses_ytd == Decimal("-20")
    assert b.realized_gains_ytd == Decimal("30")
    assert b.net_realized == Decimal("10")
    assert b.used_against_ordinary == Decimal("0")


def test_compute_offset_budget_clamps_loss_at_3000_cap(
    repo, schwab_account, seed_import,
) -> None:
    buy = Trade(account=schwab_account.display(), date=date(2026, 1, 5),
                ticker="UUUU", action="Buy", quantity=Decimal("100"),
                proceeds=Decimal("0"), cost_basis=Decimal("10000"))
    sell = Trade(account=schwab_account.display(), date=date(2026, 3, 1),
                 ticker="UUUU", action="Sell", quantity=Decimal("100"),
                 proceeds=Decimal("5000"), cost_basis=Decimal("10000"))
    seed_import(repo, schwab_account, [buy, sell])
    b = compute_offset_budget(repo=repo, year=2026)
    assert b.realized_losses_ytd == Decimal("-5000")
    assert b.used_against_ordinary == Decimal("3000")
    assert b.carryforward_projection == Decimal("2000")


def test_compute_offset_budget_planned_trades_shift_delta(
    repo, schwab_account, seed_import, seed_lots,
) -> None:
    buy = Trade(account=schwab_account.display(), date=date(2026, 1, 5),
                ticker="UUUU", action="Buy", quantity=Decimal("100"),
                proceeds=Decimal("0"), cost_basis=Decimal("1000"))
    seed_import(repo, schwab_account, [buy])
    seed_lots(repo)
    planned = [PlannedTrade(
        symbol="UUUU", account_id=schwab_account.id or 0,
        action="Sell", qty=Decimal("100"), price=Decimal("8"),
        on=date(2026, 6, 1),
    )]
    b = compute_offset_budget(repo=repo, year=2026, planned_trades=planned)
    # Planned: sell 100 at 8 vs basis 10/sh = -200 realized.
    assert b.planned_delta == Decimal("-200")
