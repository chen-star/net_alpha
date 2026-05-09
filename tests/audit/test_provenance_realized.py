from datetime import date

from net_alpha.audit.provenance import Period, RealizedPLRef, provenance_for
from net_alpha.models.domain import Trade
from net_alpha.models.realized_gl import RealizedGLLot
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
    # Per-row amount is signed realized P&L, not gross proceeds.
    assert trace.trades[0].amount == 500.0


def test_realized_provenance_breakdown_sums_to_total_with_gl_lots(repo, schwab_account):
    # Regression: when realized P/L includes broker GL lots (e.g. option
    # expirations that the Transactions CSV silently drops), the contributing
    # list must include those rows so per-row amounts reconcile to the
    # headline number. Pre-fix, the modal showed only Sell trade rows with
    # gross proceeds for amount — the breakdown didn't tie out to the total.
    sell_trade = Trade(
        account="Schwab/Tax",
        date=date(2026, 4, 9),
        ticker="PLTR",
        action="Sell",
        quantity=1.0,
        proceeds=149.34,
        cost_basis=120.00,
    )
    seed_import(repo, schwab_account, [sell_trade])

    # Add GL-only closures (e.g. expired long option, equity sell from GL CSV)
    # using the seeded import's id.
    repo.add_gl_lots(
        schwab_account,
        import_id=1,
        lots=[
            RealizedGLLot(
                account_display="Schwab/Tax",
                symbol_raw="ABC 03/15/2026 50.00 C",
                ticker="ABC",
                closed_date=date(2026, 3, 15),
                opened_date=date(2025, 11, 1),
                quantity=1.0,
                proceeds=0.0,
                cost_basis=100.00,
                unadjusted_cost_basis=100.00,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Short Term",
                option_strike=50.0,
                option_expiry="2026-03-15",
                option_call_put="C",
            ),
            RealizedGLLot(
                account_display="Schwab/Tax",
                symbol_raw="XYZ",
                ticker="XYZ",
                closed_date=date(2026, 2, 1),
                opened_date=date(2025, 6, 1),
                quantity=10.0,
                proceeds=2_000.0,
                cost_basis=1_500.0,
                unadjusted_cost_basis=1_500.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Long Term",
            ),
        ],
    )

    ref = RealizedPLRef(
        kind="realized_pl",
        period=Period(start=date(2026, 1, 1), end=date(2027, 1, 1), label="YTD 2026"),
        account_id=schwab_account.id,
        symbol=None,
    )
    trace = provenance_for(ref, repo)

    # Sell P/L: 149.34 - 120 = 29.34. Expired call: -100. Equity GL: +500.
    # Total = 429.34. Three contributing rows.
    assert len(trace.trades) == 3
    assert round(sum(t.amount for t in trace.trades), 2) == round(trace.total, 2)
    assert round(trace.total, 2) == 429.34


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
