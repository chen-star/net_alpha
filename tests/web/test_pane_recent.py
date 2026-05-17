"""Recent activity block in the positions side pane.

Tests that the `_positions_pane_recent.html` partial:
 - shows at most the 5 most recent trades
 - orders trades by date descending (newest first)
 - filters to the requested account scope
 - renders nothing when no trades exist for the symbol
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient


def _seed_buys(
    repo,
    builders,
    sym: str,
    broker: str,
    label: str,
    acquired_dates: list[date],
    qty: float = 10.0,
    cost: float = 1000.0,
) -> int:
    """Seed one buy per date, all same account/symbol. Returns account_id."""
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    account_display = f"{broker}/{label}"
    trades = [builders.make_buy(account_display, sym, d, qty=qty, cost=cost) for d in acquired_dates]
    account, _ = builders.seed_import(repo, broker, label, trades)
    stitch_account(repo, account.id)
    recompute_all_violations(repo, {})
    return account.id


# ---------------------------------------------------------------------------
# 1. At most 5 rows shown
# ---------------------------------------------------------------------------


def test_recent_activity_shows_at_most_5(client: TestClient, repo, builders) -> None:
    """Seed 8 buys at different dates → only 5 recent-row entries rendered."""
    today = date.today()
    dates = [today - timedelta(days=d * 5) for d in range(1, 9)]  # 8 distinct dates
    acct_id = _seed_buys(repo, builders, "RCNT1", "Schwab", "Taxable", dates)

    resp = client.get(f"/positions/pane?sym=RCNT1&account_id={acct_id}")
    assert resp.status_code == 200
    html = resp.text
    assert html.count('data-testid="recent-row"') == 5


# ---------------------------------------------------------------------------
# 2. Date descending order — newest first
# ---------------------------------------------------------------------------


def test_recent_activity_orders_by_date_desc(client: TestClient, repo, builders) -> None:
    """Seed 2 buys: one 30d ago, one 5d ago. Newer date must appear first."""
    today = date.today()
    older_date = today - timedelta(days=30)
    newer_date = today - timedelta(days=5)
    acct_id = _seed_buys(repo, builders, "RCNT2", "Schwab", "Taxable", [older_date, newer_date])

    resp = client.get(f"/positions/pane?sym=RCNT2&account_id={acct_id}")
    assert resp.status_code == 200
    html = resp.text

    newer_str = newer_date.isoformat()
    older_str = older_date.isoformat()
    assert newer_str in html
    assert older_str in html
    # Newer date must appear earlier in the HTML (lower find() index)
    assert html.find(newer_str) < html.find(older_str)


# ---------------------------------------------------------------------------
# 3. Account scope filter
# ---------------------------------------------------------------------------


def test_recent_activity_filters_by_account(client: TestClient, repo, builders) -> None:
    """Trades from a different account must not appear when scoped to taxable."""
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    today = date.today()
    sym = "RCNT3"

    # Taxable account: 1 buy, qty=1
    taxable_display = "Schwab/Taxable"
    buy_taxable = builders.make_buy(taxable_display, sym, today - timedelta(days=10), qty=1.0, cost=100.0)
    taxable_acct, _ = builders.seed_import(repo, "Schwab", "Taxable", [buy_taxable])
    stitch_account(repo, taxable_acct.id)

    # IRA account: 1 buy, qty=99 (distinct quantity to identify it)
    ira_display = "Schwab/IRA"
    buy_ira = builders.make_buy(ira_display, sym, today - timedelta(days=5), qty=99.0, cost=9900.0)
    ira_acct, _ = builders.seed_import(repo, "Schwab", "IRA", [buy_ira])
    stitch_account(repo, ira_acct.id)

    recompute_all_violations(repo, {})

    resp = client.get(f"/positions/pane?sym={sym}&account_id={taxable_acct.id}")
    assert resp.status_code == 200
    html = resp.text

    # Scoped to taxable: exactly 1 recent row — the IRA trade must be filtered out.
    # (The earlier `"99" not in html` check was flaky because the asset_v epoch
    # timestamp embedded in the HTML occasionally contains "99". Row count is
    # the robust assertion.)
    assert html.count('data-testid="recent-row"') == 1


# ---------------------------------------------------------------------------
# 4. Empty when no trades
# ---------------------------------------------------------------------------


def test_recent_activity_empty_when_no_trades(client: TestClient, repo) -> None:
    """No trades for the symbol → no recent-row testids rendered."""
    resp = client.get("/positions/pane?sym=NONEXIST")
    assert resp.status_code == 200
    html = resp.text
    assert 'data-testid="recent-row"' not in html
