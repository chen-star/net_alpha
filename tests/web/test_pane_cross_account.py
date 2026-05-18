"""Cross-account disambiguation: when same symbol is in 2+ accounts and
pane fetched without account_id, header shows "Across N accounts" and
lot ladder groups by account."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient


def _seed_two_accounts(repo, builders, sym: str):
    """Seed sym into Schwab/Taxable and Schwab/IRA. Returns (acct_a, acct_b)."""
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    today = date.today()
    buy_a = builders.make_buy("Schwab/Taxable", sym, today - timedelta(days=30), qty=10.0, cost=1000.0)
    buy_b = builders.make_buy("Schwab/IRA", sym, today - timedelta(days=30), qty=20.0, cost=2000.0)
    acct_a, _ = builders.seed_import(repo, "Schwab", "Taxable", [buy_a])
    acct_b, _ = builders.seed_import(repo, "Schwab", "IRA", [buy_b])
    stitch_account(repo, acct_a.id)
    stitch_account(repo, acct_b.id)
    recompute_all_violations(repo, {})
    return acct_a, acct_b


def test_header_shows_across_n_accounts(client: TestClient, repo, builders) -> None:
    """Same sym, two accounts, no account_id on the pane request → header
    shows 'Across 2 accounts'."""
    sym = "MULTI"
    _seed_two_accounts(repo, builders, sym)

    resp = client.get(f"/positions/pane?sym={sym}")  # no account_id
    assert resp.status_code == 200
    assert "Across 2 accounts" in resp.text


def test_ladder_groups_by_account_when_cross_account(client: TestClient, repo, builders) -> None:
    """Lot ladder must render per-account group sections in cross-account mode."""
    sym = "GROUP"
    _seed_two_accounts(repo, builders, sym)

    resp = client.get(f"/positions/pane?sym={sym}")
    html = resp.text
    # Exactly 2 lot-ladder-group sections
    assert html.count('data-testid="lot-ladder-group"') == 2
    # Each account display string appears
    assert "Schwab/Taxable" in html
    assert "Schwab/IRA" in html


def test_single_account_no_grouping(client: TestClient, repo, builders) -> None:
    """Only one account → no group headers, header doesn't say 'Across'."""
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    sym = "SOLO"
    today = date.today()
    buy = builders.make_buy("Schwab/Taxable", sym, today - timedelta(days=30), qty=10.0, cost=1000.0)
    acct, _ = builders.seed_import(repo, "Schwab", "Taxable", [buy])
    stitch_account(repo, acct.id)
    recompute_all_violations(repo, {})

    resp = client.get(f"/positions/pane?sym={sym}")  # no account_id
    html = resp.text
    assert "Across" not in html
    assert 'data-testid="lot-ladder-group"' not in html


def test_pane_scoped_to_one_account_does_not_group(client: TestClient, repo, builders) -> None:
    """Even if multiple accounts hold the symbol, when account_id is
    specified the pane scopes to that one account — no cross-account UI."""
    sym = "SCOPED"
    acct_a, _ = _seed_two_accounts(repo, builders, sym)

    resp = client.get(f"/positions/pane?sym={sym}&account_id={acct_a.id}")
    html = resp.text
    assert "Across" not in html
    assert 'data-testid="lot-ladder-group"' not in html
