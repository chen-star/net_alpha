from datetime import date, timedelta
from decimal import Decimal

from net_alpha.models.domain import Trade
from net_alpha.portfolio.tax_planner import (
    PlannedTrade,
    TaxBrackets,
    TaxLightSignal,
    assess_trade,
)


def test_tax_light_signal_constructs() -> None:
    s = TaxLightSignal(
        color="green",
        reason_codes=["LT_LOSS"],
        explanation="Tax-efficient — LT loss; offsets ST gains",
        suggestion=None,
        lot_method_recommended="HIFO",
    )
    assert s.color == "green"


def test_red_when_proposed_sell_triggers_wash(
    repo,
    schwab_account,
    seed_import,
    seed_lots,
) -> None:
    today = date(2026, 5, 1)
    buy = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=10),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("100"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("600"),
    )
    seed_import(repo, schwab_account, [buy])
    seed_lots(repo)
    proposed = PlannedTrade(
        symbol="UUUU",
        account_id=schwab_account.id or 0,
        action="Sell",
        qty=Decimal("100"),
        price=Decimal("4"),
        on=today,
    )
    s = assess_trade(
        proposed=proposed,
        repo=repo,
        brackets=None,
        as_of=today,
        etf_pairs={},
    )
    assert s.color == "red"
    assert "WASH_RISK" in s.reason_codes
    assert "lockout" in (s.explanation or "").lower() or "wash" in (s.explanation or "").lower()


def test_green_when_no_loss_no_wash(
    repo,
    schwab_account,
    seed_import,
    seed_lots,
) -> None:
    today = date(2026, 5, 1)
    buy = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=400),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("100"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("100"),
    )
    seed_import(repo, schwab_account, [buy])
    seed_lots(repo)
    proposed = PlannedTrade(
        symbol="UUUU",
        account_id=schwab_account.id or 0,
        action="Sell",
        qty=Decimal("100"),
        price=Decimal("8"),
        on=today,
    )
    s = assess_trade(
        proposed=proposed,
        repo=repo,
        brackets=None,
        as_of=today,
        etf_pairs={},
    )
    assert s.color == "green"
