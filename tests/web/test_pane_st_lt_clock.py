"""ST→LT clock — visible only when ≥1 open lot is ≤90d from LT.

The helper `_pane_lot_info` in positions.py is the source of truth.
The clock partial reads `lt_clock` from the ctx."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient


def _seed_basic(
    repo,
    builders,
    sym: str,
    broker: str,
    label: str,
    acquired_date: date,
) -> int:
    """Seed a single buy trade at $100 for 10 shares. Returns account_id."""
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    account_display = f"{broker}/{label}"
    trade = builders.make_buy(account_display, sym, acquired_date, qty=10.0, cost=1000.0)
    account, _ = builders.seed_import(repo, broker, label, [trade])
    stitch_account(repo, account.id)
    recompute_all_violations(repo, {})
    return account.id


def test_st_lt_clock_visible_when_within_90d(client: TestClient, repo, builders) -> None:
    """A lot acquired 280 days ago has 86d to LT — show the clock."""
    today = date.today()
    acquired = today - timedelta(days=280)
    acct_id = _seed_basic(repo, builders, "AAPL", "Schwab", "Taxable", acquired)
    resp = client.get(f"/positions/pane?sym=AAPL&account_id={acct_id}")
    assert resp.status_code == 200
    html = resp.text
    assert 'data-testid="st-lt-clock"' in html
    assert "86d to LT" in html  # 366 - 280


def test_st_lt_clock_hidden_when_no_st_lots(client: TestClient, repo, builders) -> None:
    """A lot acquired 400 days ago is already LT — clock hidden."""
    today = date.today()
    acquired = today - timedelta(days=400)
    acct_id = _seed_basic(repo, builders, "MSFT", "Schwab", "Taxable", acquired)
    resp = client.get(f"/positions/pane?sym=MSFT&account_id={acct_id}")
    assert resp.status_code == 200
    assert 'data-testid="st-lt-clock"' not in resp.text


def test_st_lt_clock_hidden_when_st_but_over_90d(client: TestClient, repo, builders) -> None:
    """A lot acquired 30 days ago is ST but 336d away — clock hidden."""
    today = date.today()
    acquired = today - timedelta(days=30)
    acct_id = _seed_basic(repo, builders, "NVDA", "Schwab", "Taxable", acquired)
    resp = client.get(f"/positions/pane?sym=NVDA&account_id={acct_id}")
    assert resp.status_code == 200
    assert 'data-testid="st-lt-clock"' not in resp.text
