"""Forward-projection planner honors §1223(4) wash-sale tacking and per-lot FIFO.

`_classify_st_lt_gains` previously used `chain[0].date` (earliest buy of the
ticker) regardless of which lot the sell actually consumed. The corrected
implementation walks lots — using ``effective_acquired_date`` for tacking —
and falls back to per-trade FIFO when no lot rows exist (e.g. test paths
that skip wash-sale recompute).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from net_alpha.models.domain import Lot, Trade
from net_alpha.portfolio.tax_planner import TaxBrackets, project_year_end_tax

_BRACKETS = TaxBrackets(
    filing_status="single",
    state="CA",
    federal_marginal_rate=Decimal("0.32"),
    state_marginal_rate=Decimal("0.093"),
    ltcg_rate=Decimal("0.15"),
    qualified_div_rate=Decimal("0.15"),
)


def test_projection_promotes_st_to_lt_via_wash_sale_tacking(
    repo,
    schwab_account,
    seed_import,
) -> None:
    """Replacement lot held 200 days raw but tacked >365 ago → LT, not ST."""
    today = date(2026, 5, 1)
    # Buy 200 days before sell (raw → ST).
    buy = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=200),
        ticker="WASH",
        action="Buy",
        quantity=Decimal("10"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("1000"),
    )
    sell = Trade(
        account=schwab_account.display(),
        date=today,
        ticker="WASH",
        action="Sell",
        quantity=Decimal("10"),
        proceeds=Decimal("2000"),
        cost_basis=Decimal("1000"),
    )
    seed_import(repo, schwab_account, [buy, sell])

    # Pretend a wash-sale recompute happened: replace the lot with one that
    # carries a tacked_acquired_date >365 days before the sell.
    win_start = today - timedelta(days=400)
    win_end = today + timedelta(days=1)
    tacked = Lot(
        trade_id="0",  # placeholder; replace_lots_in_window resolves by ticker+date
        account=schwab_account.display(),
        date=today - timedelta(days=200),
        ticker="WASH",
        quantity=10.0,
        cost_basis=1000.0,
        adjusted_basis=1000.0,
        tacked_acquired_date=today - timedelta(days=500),
    )
    # Look up the actual buy trade id and overwrite the placeholder.
    all_trades = repo.all_trades()
    buy_row = next(t for t in all_trades if t.ticker == "WASH" and t.action.lower() == "buy")
    tacked = tacked.model_copy(update={"trade_id": buy_row.id})
    repo.replace_lots_in_window(win_start, win_end, [tacked])

    p = project_year_end_tax(repo=repo, year=2026, brackets=_BRACKETS)
    # 1000 gain. With tacking → LT (taxed at 15% federal + 9.3% state).
    assert p.realized_lt_gain == Decimal("1000")
    assert p.realized_st_gain == Decimal("0")


def test_projection_fifo_with_prior_consumed_lot(
    repo,
    schwab_account,
    seed_import,
) -> None:
    """A prior sell that fully consumed b1 must remove it from FIFO for later sells."""
    today = date(2026, 5, 1)
    b1 = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=800),
        ticker="FIFO",
        action="Buy",
        quantity=Decimal("10"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("1000"),
    )
    prior_sell = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=400),
        ticker="FIFO",
        action="Sell",
        quantity=Decimal("10"),
        proceeds=Decimal("1500"),
        cost_basis=Decimal("1000"),
    )
    b2 = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=60),  # short term from b2
        ticker="FIFO",
        action="Buy",
        quantity=Decimal("10"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("1100"),
    )
    target_sell = Trade(
        account=schwab_account.display(),
        date=today,
        ticker="FIFO",
        action="Sell",
        quantity=Decimal("10"),
        proceeds=Decimal("1400"),
        cost_basis=Decimal("1100"),
    )
    seed_import(repo, schwab_account, [b1, prior_sell, b2, target_sell])

    p = project_year_end_tax(repo=repo, year=2026, brackets=_BRACKETS)
    # 300 gain on a 60-day hold (b1 already consumed by prior_sell) → ST.
    # Pre-fix this would have used b1's date (800 days) and reported LT.
    assert p.realized_st_gain == Decimal("300")
    assert p.realized_lt_gain == Decimal("0")
