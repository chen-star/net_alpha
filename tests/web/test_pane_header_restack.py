"""Header is now a two-line stack with an explicit ST/LT pill.

Line 1: identifier (sym · qty · account · last)
Line 2: status pill + value (basis + unrealized)"""

from __future__ import annotations

import re
from datetime import date, timedelta

from fastapi.testclient import TestClient


def test_header_pill_ST_when_all_lots_short_term(client: TestClient, repo, builders) -> None:
    """A lot acquired 30 days ago is ST → header pill says ST."""
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    sym = "STONLY"
    today = date.today()
    display = "Schwab/Taxable"
    buy = builders.make_buy(display, sym, today - timedelta(days=30), qty=10.0, cost=1000.0)
    acct, _ = builders.seed_import(repo, "Schwab", "Taxable", [buy])
    stitch_account(repo, acct.id)
    recompute_all_violations(repo, {})
    resp = client.get(f"/positions/pane?sym={sym}&account_id={acct.id}")
    assert resp.status_code == 200
    html = resp.text
    assert 'data-testid="pane-header-status-pill"' in html
    # The pill body must contain "ST" not "LT".
    m = re.search(r'data-testid="pane-header-status-pill"[^>]*>([^<]*)<', html)
    assert m is not None
    assert m.group(1).strip() == "ST"


def test_header_pill_LT_when_all_lots_long_term(client: TestClient, repo, builders) -> None:
    """A lot acquired 400 days ago is LT → header pill says LT."""
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    sym = "LTONLY"
    today = date.today()
    display = "Schwab/Taxable"
    buy = builders.make_buy(display, sym, today - timedelta(days=400), qty=10.0, cost=1000.0)
    acct, _ = builders.seed_import(repo, "Schwab", "Taxable", [buy])
    stitch_account(repo, acct.id)
    recompute_all_violations(repo, {})
    resp = client.get(f"/positions/pane?sym={sym}&account_id={acct.id}")
    html = resp.text
    m = re.search(r'data-testid="pane-header-status-pill"[^>]*>([^<]*)<', html)
    assert m and m.group(1).strip() == "LT"


def test_header_pill_mixed_when_both_st_and_lt(client: TestClient, repo, builders) -> None:
    """Two lots — one 30d old (ST), one 400d old (LT) → header pill says ST/LT."""
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    sym = "MIXED"
    today = date.today()
    display = "Schwab/Taxable"
    buy_st = builders.make_buy(display, sym, today - timedelta(days=30), qty=10.0, cost=1000.0)
    buy_lt = builders.make_buy(display, sym, today - timedelta(days=400), qty=10.0, cost=900.0)
    acct, _ = builders.seed_import(repo, "Schwab", "Taxable", [buy_st, buy_lt])
    stitch_account(repo, acct.id)
    recompute_all_violations(repo, {})
    resp = client.get(f"/positions/pane?sym={sym}&account_id={acct.id}")
    html = resp.text
    m = re.search(r'data-testid="pane-header-status-pill"[^>]*>([^<]*)<', html)
    assert m and m.group(1).strip() == "ST/LT"


def test_header_pill_absent_when_no_open_lots(client: TestClient) -> None:
    """No lots → no pill testid (header still renders the sym line)."""
    resp = client.get("/positions/pane?sym=NONEXIST")
    html = resp.text
    assert 'data-testid="pane-header"' in html
    assert 'data-testid="pane-header-status-pill"' not in html
