"""Lot ladder — one row per open equity lot in the positions side pane.

Tests that the `_positions_pane_lot_ladder.html` partial:
 - emits one ``data-testid="lot-row"`` per open lot
 - collapses to a "N lots" toggle when N > 5
 - uses the correct status pill (ST vs. LT)
 - exposes the tacked-lot tooltip (skipped until fixture is wired)
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient


def _seed_buys(repo, builders, sym: str, broker: str, label: str, acquired_dates: list[date]) -> int:
    """Seed one buy per date, all same account/symbol. Returns account_id."""
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    account_display = f"{broker}/{label}"
    trades = [builders.make_buy(account_display, sym, d, qty=10.0, cost=1000.0) for d in acquired_dates]
    account, _ = builders.seed_import(repo, broker, label, trades)
    stitch_account(repo, account.id)
    recompute_all_violations(repo, {})
    return account.id


# ---------------------------------------------------------------------------
# 1. One row per lot
# ---------------------------------------------------------------------------


def test_lot_ladder_one_row_per_lot(client: TestClient, repo, builders) -> None:
    """Three buys at different dates → three lot rows."""
    today = date.today()
    dates = [today - timedelta(days=d) for d in [50, 100, 200]]
    acct_id = _seed_buys(repo, builders, "LTST1", "Schwab", "Taxable", dates)

    resp = client.get(f"/positions/pane?sym=LTST1&account_id={acct_id}")
    assert resp.status_code == 200
    html = resp.text
    assert html.count('data-testid="lot-row"') == 3


# ---------------------------------------------------------------------------
# 2. Collapse above 5
# ---------------------------------------------------------------------------


def test_lot_ladder_collapses_above_5(client: TestClient, repo, builders) -> None:
    """Seven buys → collapsed toggle + "7 lots" label visible."""
    today = date.today()
    dates = [today - timedelta(days=d * 10) for d in range(1, 8)]  # 7 distinct dates
    acct_id = _seed_buys(repo, builders, "LTST2", "Schwab", "Taxable", dates)

    resp = client.get(f"/positions/pane?sym=LTST2&account_id={acct_id}")
    assert resp.status_code == 200
    html = resp.text
    assert 'data-testid="lot-ladder-collapsed"' in html
    assert "7 lots" in html


# ---------------------------------------------------------------------------
# 3. Status pills ST vs. LT
# ---------------------------------------------------------------------------


def test_lot_ladder_st_and_lt_pills(client: TestClient, repo, builders) -> None:
    """One lot 30d ago (ST) + one lot 400d ago (LT) → both pills present."""
    today = date.today()
    dates = [today - timedelta(days=30), today - timedelta(days=400)]
    acct_id = _seed_buys(repo, builders, "LTST3", "Schwab", "Taxable", dates)

    resp = client.get(f"/positions/pane?sym=LTST3&account_id={acct_id}")
    assert resp.status_code == 200
    html = resp.text
    assert 'data-pill="ST"' in html
    assert 'data-pill="LT"' in html


# ---------------------------------------------------------------------------
# 4. Tacked pill — deferred (fixture requires a wash-sale that tacks §1223(4))
# ---------------------------------------------------------------------------


def test_lot_ladder_tacked_pill_has_tooltip(client: TestClient, repo, builders) -> None:
    """A lot whose tacked_acquired_date is set (§1223(4) wash-sale tacking) must
    render data-pill="TACKED" with a title tooltip mentioning IRC §1223(4).

    Scenario:
      1. Buy 100 sh @ $100 (2 years ago, D1) — original lot, solidly LT.
      2. Sell 100 sh @ $50 (30 days ago, D2) — $5,000 loss, triggers wash sale.
      3. Buy 100 sh @ $50 (10 days ago, D3) — replacement within ±30d of D2.

    Engine detects the wash sale: disallowed loss ($5,000) rolls into the
    replacement lot's basis ($10,000), and tacked_acquired_date is set to D1.
    The lot ladder must then render the TACKED pill + §1223(4) tooltip.
    """
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    sym = "TACK"
    today = date.today()
    display = "Schwab/Taxable"

    # Step 1: BUY 100 @ $100 two years ago — holding-period anchor for tacking.
    far_past = today - timedelta(days=730)
    buy_old = builders.make_buy(display, sym, far_past, qty=100.0, cost=10_000.0)

    # Step 2: SELL 100 @ $50 thirty days ago — realises a $5,000 loss. Pass
    # cost=10_000 explicitly so a reader can see "proceeds 5000 - cost 10000
    # = -5000 loss" at the call site, without having to trace stitch_account
    # (which would also overwrite cost_basis from the FIFO buy lot below).
    sell_date = today - timedelta(days=30)
    sell_old = builders.make_sell(display, sym, sell_date, qty=100.0, cost=10_000.0, proceeds=5_000.0)

    # Step 3: BUY 100 @ $50 ten days ago — replacement lot within ±30d of the sell.
    rebuy_date = today - timedelta(days=10)
    rebuy = builders.make_buy(display, sym, rebuy_date, qty=100.0, cost=5_000.0)

    acct, _ = builders.seed_import(repo, "Schwab", "Taxable", [buy_old, sell_old, rebuy])
    stitch_account(repo, acct.id)
    recompute_all_violations(repo, {})

    # Sanity: at least one lot for this ticker+account must have
    # tacked_acquired_date == far_past (the replacement lot).
    lots = repo.get_lots_for_ticker(sym)
    tacked_lots = [
        lot for lot in lots
        if lot.account == display and lot.tacked_acquired_date is not None
    ]
    assert len(tacked_lots) == 1, (
        f"expected exactly 1 tacked lot, got {len(tacked_lots)}: {tacked_lots}"
    )
    tacked_lot = tacked_lots[0]
    assert tacked_lot.tacked_acquired_date == far_past, (
        f"expected tacked_acquired_date={far_past}, got {tacked_lot.tacked_acquired_date}"
    )

    # Hit the pane and confirm the TACKED pill renders with the §1223(4) tooltip.
    resp = client.get(f"/positions/pane?sym={sym}&account_id={acct.id}")
    assert resp.status_code == 200
    html = resp.text
    assert 'data-pill="TACKED"' in html, "TACKED status pill not found in lot ladder"
    assert "Holding period tacked" in html, "Tooltip text 'Holding period tacked' not found"
    assert "1223(4)" in html, "IRC §1223(4) citation not found in tooltip"
