"""Wash-sale outlook block in the positions side pane.

Tests that the `_positions_pane_ws_outlook.html` partial:
 - renders data-testid="ws-outlook" with data-state="clean" when no violation
 - renders data-state="trigger" with wash-sale language when a blocking buy exists
 - omits the testid wrapper entirely when there is no open qty
 - responds in under 400ms (soft regression guard)
"""

from __future__ import annotations

import datetime as dt
import time
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient


def _seed_price(engine, sym: str, price: float) -> None:
    """Inject a cached quote so the pane has a real last_price."""
    from net_alpha.pricing.cache import PriceCache
    from net_alpha.pricing.provider import Quote

    cache = PriceCache(engine)
    cache.put_many([Quote(symbol=sym, price=Decimal(str(price)), as_of=dt.datetime.now(dt.UTC), source="test")])


def _seed_ws_trigger(repo, builders, engine, sym: str, broker: str, label: str) -> int:
    """Seed an open buy 100d ago + a replacement buy 5d ago.

    The older lot has cost $200/sh; price is seeded at $100/sh — selling
    at $100 yields a loss.  The replacement buy is 5d ago (within ±30d of
    today), so simulate_sell finds it as a blocking buy and returns
    would_trigger_wash_sale=True.

    Returns account_id.
    """
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    today = date.today()
    account_display = f"{broker}/{label}"

    # Older lot: 10 sh at $200/sh → $2 000 total cost
    buy_old = builders.make_buy(account_display, sym, today - timedelta(days=100), qty=10.0, cost=2000.0)
    # Recent replacement buy (5d ago) — same ticker, within ±30d of today
    buy_recent = builders.make_buy(account_display, sym, today - timedelta(days=5), qty=5.0, cost=800.0)
    account, _ = builders.seed_import(repo, broker, label, [buy_old, buy_recent])
    stitch_account(repo, account.id)
    recompute_all_violations(repo, {})

    # Price at $100/sh — below the $200/sh basis, ensuring a realized loss
    _seed_price(engine, sym, 100.0)
    return account.id


def _seed_clean(repo, builders, engine, sym: str, broker: str, label: str) -> int:
    """Seed a single buy 200d ago with no other recent activity.

    No replacement buys within ±30d → simulate_sell returns
    would_trigger_wash_sale=False → state="clean".

    Returns account_id.
    """
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    today = date.today()
    account_display = f"{broker}/{label}"

    # 10 sh at $150/sh → $1 500 total cost
    buy = builders.make_buy(account_display, sym, today - timedelta(days=200), qty=10.0, cost=1500.0)
    account, _ = builders.seed_import(repo, broker, label, [buy])
    stitch_account(repo, account.id)
    recompute_all_violations(repo, {})

    # Price at $80/sh — below basis so it IS a loss, but no replacement buys
    # within ±30d means no blocking buy → simulate_sell.would_trigger = False
    _seed_price(engine, sym, 80.0)
    return account.id


# ---------------------------------------------------------------------------
# 1. Clean state — testid present, data-state="clean"
# ---------------------------------------------------------------------------


def test_ws_outlook_clean_state(client: TestClient, repo, builders, engine) -> None:
    """Single buy 200d ago, no recent activity → clean state rendered."""
    acct_id = _seed_clean(repo, builders, engine, "WSCLN1", "Schwab", "Taxable")

    resp = client.get(f"/positions/pane?sym=WSCLN1&account_id={acct_id}")
    assert resp.status_code == 200
    html = resp.text

    assert 'data-testid="ws-outlook"' in html
    assert 'data-state="clean"' in html


# ---------------------------------------------------------------------------
# 2. Trigger state — wash sale language + disallowed mention
# ---------------------------------------------------------------------------


def test_ws_outlook_trigger_state(client: TestClient, repo, builders, engine) -> None:
    """Buy 100d ago + replacement buy 5d ago → trigger state with wash-sale language."""
    acct_id = _seed_ws_trigger(repo, builders, engine, "WSTRG1", "Schwab", "Taxable")

    resp = client.get(f"/positions/pane?sym=WSTRG1&account_id={acct_id}")
    assert resp.status_code == 200
    html = resp.text

    assert 'data-state="trigger"' in html
    assert "wash sale" in html.lower()
    assert "disallowed" in html.lower()


# ---------------------------------------------------------------------------
# 3. Skipped state — no testid when no open qty
# ---------------------------------------------------------------------------


def test_ws_outlook_skipped_when_no_open_qty(client: TestClient, repo) -> None:
    """No seeded data for the symbol → no open qty → ws-outlook not rendered."""
    resp = client.get("/positions/pane?sym=NONEXIST")
    assert resp.status_code == 200
    html = resp.text

    assert 'data-testid="ws-outlook"' not in html


# ---------------------------------------------------------------------------
# 4. Latency sanity — under 400ms
# ---------------------------------------------------------------------------


def test_pane_render_under_400ms(client: TestClient, repo, builders, engine) -> None:
    """Trigger fixture completes pane render in under 400ms."""
    acct_id = _seed_ws_trigger(repo, builders, engine, "WSLAT1", "Schwab", "Taxable")

    t0 = time.perf_counter()
    resp = client.get(f"/positions/pane?sym=WSLAT1&account_id={acct_id}")
    elapsed = time.perf_counter() - t0

    assert resp.status_code == 200
    assert elapsed < 0.4, f"Pane render took {elapsed:.3f}s — over 400ms budget"
