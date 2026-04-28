from __future__ import annotations

from datetime import date

from net_alpha.audit.reconciliation import ReconciliationStatus, reconcile
from net_alpha.models.domain import Trade
from net_alpha.models.realized_gl import RealizedGLLot
from tests.audit.conftest import seed_import


def test_reconcile_clean_match(repo, schwab_account):
    seed_import(
        repo,
        schwab_account,
        [
            Trade(
                account="Schwab/Tax", date=date(2026, 1, 1), ticker="AAPL", action="Buy", quantity=10, cost_basis=1000.0
            ),
            Trade(
                account="Schwab/Tax",
                date=date(2026, 4, 1),
                ticker="AAPL",
                action="Sell",
                quantity=10,
                proceeds=1500.0,
                cost_basis=1000.0,
            ),
        ],
    )
    repo.add_gl_lots(
        schwab_account,
        import_id=1,
        lots=[
            RealizedGLLot(
                account_display="Schwab/Tax",
                symbol_raw="AAPL",
                ticker="AAPL",
                closed_date=date(2026, 4, 1),
                opened_date=date(2026, 1, 1),
                quantity=10.0,
                proceeds=1500.0,
                cost_basis=1000.0,
                unadjusted_cost_basis=1000.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Long Term",
            )
        ],
    )

    r = reconcile(symbol="AAPL", account_id=schwab_account.id, repo=repo)
    assert r.status == ReconciliationStatus.MATCH
    assert r.net_alpha_total == 500.0
    assert r.broker_total == 500.0
    assert r.delta == 0.0


def test_reconcile_within_tolerance(repo, schwab_account):
    seed_import(
        repo,
        schwab_account,
        [
            Trade(
                account="Schwab/Tax", date=date(2026, 1, 1), ticker="AAPL", action="Buy", quantity=10, cost_basis=1000.0
            ),
            Trade(
                account="Schwab/Tax",
                date=date(2026, 4, 1),
                ticker="AAPL",
                action="Sell",
                quantity=10,
                proceeds=1500.0,
                cost_basis=1000.0,
            ),
        ],
    )
    repo.add_gl_lots(
        schwab_account,
        import_id=1,
        lots=[
            RealizedGLLot(
                account_display="Schwab/Tax",
                symbol_raw="AAPL",
                ticker="AAPL",
                closed_date=date(2026, 4, 1),
                opened_date=date(2026, 1, 1),
                quantity=10.0,
                proceeds=1500.0,
                cost_basis=999.70,  # $0.30 short
                unadjusted_cost_basis=999.70,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Long Term",
            )
        ],
    )

    r = reconcile(symbol="AAPL", account_id=schwab_account.id, repo=repo, tolerance=0.50)
    assert r.status == ReconciliationStatus.NEAR_MATCH
    assert abs(r.delta) < 0.50


def test_reconcile_diff_exceeds_tolerance(repo, schwab_account):
    seed_import(
        repo,
        schwab_account,
        [
            Trade(
                account="Schwab/Tax", date=date(2026, 1, 1), ticker="AAPL", action="Buy", quantity=10, cost_basis=1000.0
            ),
            Trade(
                account="Schwab/Tax",
                date=date(2026, 4, 1),
                ticker="AAPL",
                action="Sell",
                quantity=10,
                proceeds=1500.0,
                cost_basis=1000.0,
            ),
        ],
    )
    repo.add_gl_lots(
        schwab_account,
        import_id=1,
        lots=[
            RealizedGLLot(
                account_display="Schwab/Tax",
                symbol_raw="AAPL",
                ticker="AAPL",
                closed_date=date(2026, 4, 1),
                opened_date=date(2026, 1, 1),
                quantity=10.0,
                proceeds=1498.80,
                cost_basis=1000.0,
                unadjusted_cost_basis=1000.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Long Term",
            )
        ],
    )

    r = reconcile(symbol="AAPL", account_id=schwab_account.id, repo=repo, tolerance=0.50)
    assert r.status == ReconciliationStatus.DIFF
    assert abs(r.delta) > 0.50


def test_reconcile_no_provider_returns_unavailable(repo):
    fid = repo.get_or_create_account(broker="Fidelity", label="Roth")
    r = reconcile(symbol="AAPL", account_id=fid.id, repo=repo)
    assert r.status == ReconciliationStatus.UNAVAILABLE
    assert r.broker_total is None
