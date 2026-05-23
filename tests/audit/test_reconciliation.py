from __future__ import annotations

from datetime import date

from net_alpha.audit.reconciliation import ReconciliationStatus, reconcile, reconcile_all
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


def test_reconcile_tax_year_scope_matches_broker_ytd(repo, schwab_account):
    """Audit #15: when the user imports only one year of broker G/L but has
    multi-year trades, the default lifetime-scope `reconcile()` reports a
    spurious DIFF equal to prior years' P&L. Passing `tax_year=<broker year>`
    must narrow net-alpha's side to the same scope and yield MATCH.
    """
    seed_import(
        repo,
        schwab_account,
        [
            # 2024 trade — not represented in the 2025 broker file below.
            Trade(
                account="Schwab/Tax",
                date=date(2024, 1, 5),
                ticker="AAPL",
                action="Buy",
                quantity=10,
                cost_basis=1000.0,
            ),
            Trade(
                account="Schwab/Tax",
                date=date(2024, 6, 1),
                ticker="AAPL",
                action="Sell",
                quantity=10,
                proceeds=1100.0,
                cost_basis=1000.0,
            ),
            # 2025 trade — covered by the broker file.
            Trade(
                account="Schwab/Tax",
                date=date(2025, 1, 5),
                ticker="AAPL",
                action="Buy",
                quantity=10,
                cost_basis=1200.0,
            ),
            Trade(
                account="Schwab/Tax",
                date=date(2025, 4, 1),
                ticker="AAPL",
                action="Sell",
                quantity=10,
                proceeds=1500.0,
                cost_basis=1200.0,
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
                closed_date=date(2025, 4, 1),
                opened_date=date(2025, 1, 5),
                quantity=10.0,
                proceeds=1500.0,
                cost_basis=1200.0,
                unadjusted_cost_basis=1200.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Short Term",
            ),
        ],
    )

    # Lifetime scope (default) — DIFF because net-alpha sums 2024 + 2025 = $400
    # but broker only covers 2025 = $300.
    lifetime = reconcile(symbol="AAPL", account_id=schwab_account.id, repo=repo)
    assert lifetime.status == ReconciliationStatus.DIFF
    assert lifetime.net_alpha_total == 400.0
    assert lifetime.broker_total == 300.0

    # Year-scoped — MATCH on the broker's year.
    scoped = reconcile(symbol="AAPL", account_id=schwab_account.id, repo=repo, tax_year=2025)
    assert scoped.status == ReconciliationStatus.MATCH
    assert scoped.net_alpha_total == 300.0
    assert scoped.broker_total == 300.0
    assert scoped.delta == 0.0


def test_reconcile_all_forwards_tax_year(repo, schwab_account):
    """Audit #15 follow-up: the batch wrapper must forward ``tax_year`` to
    every per-symbol ``reconcile()`` call. Without the forward, the engine
    side stayed lifetime-scoped even when downstream callers passed the
    page-level year.
    """
    seed_import(
        repo,
        schwab_account,
        [
            # 2024 trade that the 2025 broker file does NOT cover.
            Trade(
                account="Schwab/Tax",
                date=date(2024, 1, 5),
                ticker="AAPL",
                action="Buy",
                quantity=10,
                cost_basis=1000.0,
            ),
            Trade(
                account="Schwab/Tax",
                date=date(2024, 6, 1),
                ticker="AAPL",
                action="Sell",
                quantity=10,
                proceeds=1100.0,
                cost_basis=1000.0,
            ),
            # 2025 trade — covered by the broker file.
            Trade(
                account="Schwab/Tax",
                date=date(2025, 1, 5),
                ticker="AAPL",
                action="Buy",
                quantity=10,
                cost_basis=1200.0,
            ),
            Trade(
                account="Schwab/Tax",
                date=date(2025, 4, 1),
                ticker="AAPL",
                action="Sell",
                quantity=10,
                proceeds=1500.0,
                cost_basis=1200.0,
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
                closed_date=date(2025, 4, 1),
                opened_date=date(2025, 1, 5),
                quantity=10.0,
                proceeds=1500.0,
                cost_basis=1200.0,
                unadjusted_cost_basis=1200.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Short Term",
            ),
        ],
    )

    lifetime = reconcile_all(repo=repo)
    assert len(lifetime) == 1
    assert lifetime[0].status == ReconciliationStatus.DIFF
    assert lifetime[0].net_alpha_total == 400.0

    scoped = reconcile_all(repo=repo, tax_year=2025)
    assert len(scoped) == 1
    assert scoped[0].status == ReconciliationStatus.MATCH
    assert scoped[0].net_alpha_total == 300.0
    assert scoped[0].broker_total == 300.0
