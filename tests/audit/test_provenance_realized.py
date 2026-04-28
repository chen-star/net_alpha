from datetime import date

from net_alpha.audit.provenance import Period, RealizedPLRef, provenance_for
from net_alpha.models.domain import Trade
from tests.audit.conftest import seed_import


def test_realized_provenance_filters_by_period_and_symbol(repo, schwab_account):
    # Two AAPL sells (one in scope, one out), one MSFT sell (different symbol).
    trades_in = [
        Trade(account="Schwab/Tax", date=date(2026, 3, 1), ticker="AAPL", action="Buy", quantity=10, cost_basis=1000.0),
        Trade(
            account="Schwab/Tax",
            date=date(2026, 4, 1),
            ticker="AAPL",
            action="Sell",
            quantity=10,
            proceeds=1500.0,
            cost_basis=1000.0,
        ),
        Trade(
            account="Schwab/Tax",
            date=date(2025, 12, 1),
            ticker="AAPL",
            action="Sell",
            quantity=5,
            proceeds=600.0,
            cost_basis=400.0,
        ),
        Trade(
            account="Schwab/Tax",
            date=date(2026, 4, 1),
            ticker="MSFT",
            action="Sell",
            quantity=5,
            proceeds=2000.0,
            cost_basis=1500.0,
        ),
    ]
    seed_import(repo, schwab_account, trades_in)

    ref = RealizedPLRef(
        kind="realized_pl",
        period=Period(start=date(2026, 1, 1), end=date(2027, 1, 1), label="YTD 2026"),
        account_id=schwab_account.id,
        symbol="AAPL",
    )
    trace = provenance_for(ref, repo)

    # Exactly one in-scope sell (2026-04-01 AAPL), realized = 500.
    assert len(trace.trades) == 1
    assert trace.trades[0].symbol == "AAPL"
    assert trace.trades[0].action == "Sell"
    assert trace.total == 500.0


def test_realized_provenance_aggregate_account(repo, schwab_account):
    # account_id=None means aggregate across accounts.
    trades = [
        Trade(
            account="Schwab/Tax",
            date=date(2026, 4, 1),
            ticker="AAPL",
            action="Sell",
            quantity=10,
            proceeds=1500.0,
            cost_basis=1000.0,
        ),
    ]
    seed_import(repo, schwab_account, trades)

    ref = RealizedPLRef(
        kind="realized_pl",
        period=Period(start=date(2026, 1, 1), end=date(2027, 1, 1), label="YTD 2026"),
        account_id=None,
        symbol=None,
    )
    trace = provenance_for(ref, repo)
    assert trace.total == 500.0
    assert len(trace.trades) == 1
