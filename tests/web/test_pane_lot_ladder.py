"""Lot ladder — one row per open equity lot in the positions side pane.

Tests that the `_positions_pane_lot_ladder.html` partial:
 - emits one ``data-testid="lot-row"`` per open lot
 - collapses to a "N lots" toggle when N > 5
 - uses the correct status pill (ST vs. LT)
 - exposes the tacked-lot tooltip (skipped until fixture is wired)
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
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


@pytest.mark.skip(reason="tacked-lot fixture not yet wired")
def test_lot_ladder_tacked_pill_has_tooltip(client: TestClient, repo, builders) -> None:  # pragma: no cover
    """A lot whose tacked_acquired_date is set should render data-pill="TACKED"
    with a title tooltip mentioning IRC §1223(4)."""
    # Seeding a wash-sale + replacement that triggers §1223(4) tacking requires
    # a multi-step fixture (sell at loss, buy within 30d, recompute). Wire the
    # fixture here once the wash-sale seeder helper is available.
    pytest.skip("tacked-lot fixture not yet wired")
