"""QA-audit regression tests for reconciliation bugs.

Covers:
  * C1 — same-day sells were collapsed by a dict-comprehension in per_lot_diffs,
         producing simultaneous false-positive + false-negative findings.
  * H1 — `_net_alpha_realized` skipped BTC closes (action="buy" w/
         basis_source ∈ option_short_close*), under-counting realized P&L for
         options accounts.
"""

from __future__ import annotations

from datetime import date

from net_alpha.audit.reconciliation import ReconciliationStatus, per_lot_diffs, reconcile
from net_alpha.models.domain import Trade
from net_alpha.models.realized_gl import RealizedGLLot
from tests.audit.conftest import seed_import


def test_same_day_sells_are_not_collapsed_in_per_lot_diffs(repo, schwab_account):
    """Two net-alpha sells on the same date must each match against one of the
    two broker lots that share that closed_date — previously the second sell
    was silently overwritten by the first in a dict-comprehension, causing the
    second broker lot to flag 'net-alpha has no matching sell on this date'.
    """
    seed_import(
        repo,
        schwab_account,
        [
            Trade(
                account="Schwab/Tax", date=date(2026, 1, 1), ticker="AAPL", action="Buy", quantity=60, cost_basis=6000.0
            ),
            Trade(
                account="Schwab/Tax", date=date(2026, 1, 1), ticker="AAPL", action="Buy", quantity=40, cost_basis=4000.0
            ),
            # Two same-day partial-fill sells, one per lot:
            Trade(
                account="Schwab/Tax",
                date=date(2026, 4, 1),
                ticker="AAPL",
                action="Sell",
                quantity=60,
                proceeds=9000.0,
                cost_basis=6000.0,
            ),
            Trade(
                account="Schwab/Tax",
                date=date(2026, 4, 1),
                ticker="AAPL",
                action="Sell",
                quantity=40,
                proceeds=6000.0,
                cost_basis=4000.0,
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
                quantity=60.0,
                proceeds=9000.0,
                cost_basis=6000.0,
                unadjusted_cost_basis=6000.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Long Term",
            ),
            RealizedGLLot(
                account_display="Schwab/Tax",
                symbol_raw="AAPL",
                ticker="AAPL",
                closed_date=date(2026, 4, 1),
                opened_date=date(2026, 1, 1),
                quantity=40.0,
                proceeds=6000.0,
                cost_basis=4000.0,
                unadjusted_cost_basis=4000.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Long Term",
            ),
        ],
    )

    diffs = per_lot_diffs(symbol="AAPL", account_id=schwab_account.id, repo=repo)
    assert len(diffs) == 2
    # Each broker lot must match against a real net-alpha sell — no "no match"
    # rows should appear.
    for d in diffs:
        assert d.likely_cause != "net-alpha has no matching sell on this date"
        assert d.net_alpha_basis is not None
        assert abs(d.delta) < 0.005  # clean match


def test_net_alpha_realized_includes_buy_to_close_options(repo, schwab_account):
    """STO premium received minus BTC closing cost should appear in net-alpha's
    realized total. Before the fix, only the STO leg contributed and BTC was
    excluded as 'not a sell', so net-alpha always disagreed with broker by the
    closing cost.
    """
    seed_import(
        repo,
        schwab_account,
        [
            # STO: sold a put for $5.00 (premium $500).
            Trade(
                account="Schwab/Tax",
                date=date(2026, 1, 15),
                ticker="XYZ",
                action="Sell",
                quantity=1,
                proceeds=500.0,
                cost_basis=0.0,
                basis_source="option_short_open",
            ),
            # BTC: bought to close at $2.00 (cost $200).
            Trade(
                account="Schwab/Tax",
                date=date(2026, 2, 15),
                ticker="XYZ",
                action="Buy",
                quantity=1,
                proceeds=0.0,
                cost_basis=200.0,
                basis_source="option_short_close",
            ),
        ],
    )
    # Broker reports the realized net of the STO/BTC pair as $300.
    repo.add_gl_lots(
        schwab_account,
        import_id=1,
        lots=[
            RealizedGLLot(
                account_display="Schwab/Tax",
                symbol_raw="XYZ",
                ticker="XYZ",
                closed_date=date(2026, 2, 15),
                opened_date=date(2026, 1, 15),
                quantity=1.0,
                proceeds=500.0,
                cost_basis=200.0,
                unadjusted_cost_basis=200.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Short Term",
            )
        ],
    )

    r = reconcile(symbol="XYZ", account_id=schwab_account.id, repo=repo)
    # Net-alpha realized = $500 (STO) - $200 (BTC) = $300. Broker = $300.
    assert r.net_alpha_total == 300.0
    assert r.broker_total == 300.0
    assert r.status == ReconciliationStatus.MATCH
