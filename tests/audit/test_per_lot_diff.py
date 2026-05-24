from __future__ import annotations

from datetime import date

from net_alpha.audit.reconciliation import per_lot_diffs
from net_alpha.models.domain import Trade
from net_alpha.models.realized_gl import RealizedGLLot
from tests.audit.conftest import seed_import


def test_per_lot_diff_pro_rates_one_sell_across_multiple_broker_lots(repo, schwab_account):
    """Audit #34: when one net-alpha sell is split by the broker into N G/L
    lots (e.g., HIFO allocates the close across multiple acquisition dates),
    the per_lot_diffs fallback ``bucket[0]`` + ``bucket.remove`` treats the
    first broker lot's qty as the full sell — every subsequent broker lot
    becomes orphaned and every delta is wildly wrong.

    Fix: pro-rate the net-alpha sell across the broker lots by
    ``bl.qty / total_broker_qty`` so each LotDiff carries the matched
    fraction of net-alpha proceeds + basis, and the deltas sum to the
    single-lot delta within $0.01.
    """
    # Two buys totaling 100 shares, then one sell of 100 — net-alpha sees a
    # single sell row; broker splits the close into three G/L lots (40/35/25).
    seed_import(
        repo,
        schwab_account,
        [
            Trade(
                account="Schwab/Tax",
                date=date(2025, 1, 5),
                ticker="AAPL",
                action="Buy",
                quantity=100,
                cost_basis=2000.0,
            ),
            Trade(
                account="Schwab/Tax",
                date=date(2025, 6, 1),
                ticker="AAPL",
                action="Sell",
                quantity=100,
                proceeds=5000.0,
                cost_basis=2000.0,
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
                closed_date=date(2025, 6, 1),
                opened_date=date(2024, 1, 10),
                quantity=40.0,
                proceeds=2000.0,
                cost_basis=800.0,
                unadjusted_cost_basis=800.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Long Term",
            ),
            RealizedGLLot(
                account_display="Schwab/Tax",
                symbol_raw="AAPL",
                ticker="AAPL",
                closed_date=date(2025, 6, 1),
                opened_date=date(2024, 6, 15),
                quantity=35.0,
                proceeds=1750.0,
                cost_basis=700.0,
                unadjusted_cost_basis=700.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Long Term",
            ),
            RealizedGLLot(
                account_display="Schwab/Tax",
                symbol_raw="AAPL",
                ticker="AAPL",
                closed_date=date(2025, 6, 1),
                opened_date=date(2025, 1, 5),
                quantity=25.0,
                proceeds=1250.0,
                cost_basis=500.0,
                unadjusted_cost_basis=500.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Short Term",
            ),
        ],
    )

    diffs = per_lot_diffs(symbol="AAPL", account_id=schwab_account.id, repo=repo)

    # Three broker lots → three LotDiffs (one per broker row). None should be
    # orphaned with net_alpha_basis=None.
    assert len(diffs) == 3
    assert all(d.net_alpha_basis is not None for d in diffs), (
        f"expected pro-rated net-alpha values on every LotDiff; got {[d.net_alpha_basis for d in diffs]}"
    )

    # Each LotDiff's net-alpha values should be the matched fraction:
    #   bl.qty / 100 × (net-alpha proceeds, net-alpha basis)
    by_qty = {d.qty: d for d in diffs}
    expected = {
        40.0: (5000.0 * 40 / 100, 2000.0 * 40 / 100),  # (2000, 800)
        35.0: (5000.0 * 35 / 100, 2000.0 * 35 / 100),  # (1750, 700)
        25.0: (5000.0 * 25 / 100, 2000.0 * 25 / 100),  # (1250, 500)
    }
    for qty, (na_proc, na_basis) in expected.items():
        d = by_qty[qty]
        assert abs((d.net_alpha_proceeds or 0.0) - na_proc) < 0.01, (
            f"qty={qty}: net_alpha_proceeds {d.net_alpha_proceeds} ≠ pro-rated {na_proc}"
        )
        assert abs((d.net_alpha_basis or 0.0) - na_basis) < 0.01, (
            f"qty={qty}: net_alpha_basis {d.net_alpha_basis} ≠ pro-rated {na_basis}"
        )

    # The pro-rated deltas must sum to the single-lot delta (which is 0 here
    # since broker totals = net-alpha totals: $5000 proceeds, $2000 basis,
    # $3000 P&L on both sides).
    assert abs(sum(d.delta for d in diffs)) < 0.01


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
