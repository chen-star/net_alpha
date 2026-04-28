from __future__ import annotations

from datetime import date

from net_alpha.audit.reconciliation import per_lot_diffs
from net_alpha.models.domain import Trade
from net_alpha.models.realized_gl import RealizedGLLot
from tests.audit.conftest import seed_import


def test_per_lot_diff_pairs_by_close_date(repo, schwab_account):
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
                cost_basis=999.20,  # $0.80 short
                unadjusted_cost_basis=999.20,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Long Term",
            )
        ],
    )
    diffs = per_lot_diffs(symbol="AAPL", account_id=schwab_account.id, repo=repo)
    assert len(diffs) == 1
    d = diffs[0]
    assert abs(d.delta) > 0.5
    assert d.likely_cause is not None
    assert d.broker_basis == 999.20
