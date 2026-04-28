from datetime import date

from net_alpha.audit.provenance import Period, WashImpactRef, provenance_for
from net_alpha.models.domain import Trade, WashSaleViolation
from tests.audit.conftest import seed_import


def test_wash_impact_provenance_lists_violations_in_period(repo, schwab_account):
    trades = [
        Trade(
            account="Schwab/Tax",
            date=date(2026, 3, 1),
            ticker="AAPL",
            action="Sell",
            quantity=10,
            proceeds=900.0,
            cost_basis=1000.0,
        ),
        Trade(account="Schwab/Tax", date=date(2026, 3, 15), ticker="AAPL", action="Buy", quantity=10, cost_basis=950.0),
    ]
    seed_import(repo, schwab_account, trades)

    # Fetch the DB-assigned integer IDs for the seeded trades.
    all_trades = repo.all_trades()
    loss_trade = next(t for t in all_trades if t.action == "Sell")
    repl_trade = next(t for t in all_trades if t.action == "Buy")

    repo.replace_violations_in_window(
        date(2026, 1, 1),
        date(2027, 1, 1),
        [
            WashSaleViolation(
                id="v1",
                loss_trade_id=loss_trade.id,
                replacement_trade_id=repl_trade.id,
                confidence="Confirmed",
                disallowed_loss=100.0,
                matched_quantity=10.0,
                loss_account="Schwab/Tax",
                buy_account="Schwab/Tax",
                loss_sale_date=date(2026, 3, 1),
                triggering_buy_date=date(2026, 3, 15),
                ticker="AAPL",
            )
        ],
    )

    ref = WashImpactRef(
        kind="wash_impact",
        period=Period(start=date(2026, 1, 1), end=date(2027, 1, 1), label="YTD 2026"),
        account_id=schwab_account.id,
    )
    trace = provenance_for(ref, repo)
    assert trace.total == 100.0
    assert len(trace.adjustments) == 1
    assert trace.adjustments[0].rolled_amount == 100.0
    assert trace.adjustments[0].confidence == "Confirmed"
    assert "Pub 550" in trace.adjustments[0].rule_citation
