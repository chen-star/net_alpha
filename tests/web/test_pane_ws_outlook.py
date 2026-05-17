"""Wash-sale outlook block in the positions side pane.

Tests that the `_positions_pane_ws_outlook.html` partial:
 - renders data-testid="ws-outlook" with data-state="clean" when no violation
 - renders data-state="trigger" with wash-sale language when a blocking buy exists
 - omits the testid wrapper entirely when there is no open qty
 - responds in under 400ms (soft regression guard)
 - computes proportional disallowed amount correctly in partial-wash cases
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


# ---------------------------------------------------------------------------
# 5. Partial wash sale — disallowed amount is proportional to blocking qty
# ---------------------------------------------------------------------------


def test_ws_outlook_partial_disallowed_amount(client: TestClient, repo, builders, engine) -> None:
    """Partial wash: 10-share replacement buy on a 100-share open position.

    Scenario:
      - Open lot: 100 shares bought 100 days ago at $200/sh → cost basis $20,000
      - Replacement buy: 10 shares bought 5 days ago at $150/sh
      - Today's price: $100/sh → realized loss if sold = 100 × ($100 − $200) = −$10,000
      - Blocking qty covers 10/100 = 10% of sold qty
      - Proportional disallowed = 10% × $10,000 = $1,000

    The old code used abs(realized_pnl) = $10,000 (overstated by 10×).
    The fixed code should show ~$1,000, not $10,000.
    """
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    today = date.today()
    sym = "WSPRT1"
    account_display = "Schwab/Taxable"

    # Open lot: 100 sh at $200/sh → $20,000 total cost
    buy_old = builders.make_buy(account_display, sym, today - timedelta(days=100), qty=100.0, cost=20000.0)
    # Replacement buy: only 10 sh at $150/sh — partial coverage
    buy_recent = builders.make_buy(account_display, sym, today - timedelta(days=5), qty=10.0, cost=1500.0)
    account, _ = builders.seed_import(repo, "Schwab", "Taxable", [buy_old, buy_recent])
    stitch_account(repo, account.id)
    recompute_all_violations(repo, {})

    # Price at $100/sh → loss = 100 × ($100 − $200) = −$10,000 if fully disallowed
    _seed_price(engine, sym, 100.0)

    resp = client.get(f"/positions/pane?sym={sym}&account_id={account.id}")
    assert resp.status_code == 200
    html = resp.text

    # Must be in trigger state
    assert 'data-state="trigger"' in html

    # Proportional disallowed ≈ $1,000 (10% of $10,000).
    # Scope the check to the ws-outlook div so lot-ladder values don't interfere.
    # Extract just the ws-outlook block text to isolate the disallowed figure.
    import re

    outlook_match = re.search(
        r'data-testid="ws-outlook".*?</div>\s*</div>',
        html,
        re.DOTALL,
    )
    assert outlook_match, "ws-outlook div not found in response"
    outlook_html = outlook_match.group(0)

    # The full-loss figure ($10,000 — old overstated code) must NOT appear in the
    # outlook message. The correct proportional amount is ≈ $954.55
    # (10/110 × $10,500 total unrealized loss on the combined 110 sh position).
    assert "$10,000" not in outlook_html, "Overstated full-loss disallowed amount must not appear in outlook"
    # The proportional figure must be under $2,000 (far below the full-loss $10,000+).
    disallowed_match = re.search(r"\$([0-9,]+\.[0-9]{2}) disallowed", outlook_html)
    assert disallowed_match, "Expected 'disallowed' dollar amount in outlook message"
    disallowed_dollars = float(disallowed_match.group(1).replace(",", ""))
    assert disallowed_dollars < 2000, (
        f"Disallowed amount ${disallowed_dollars:,.2f} is too large — "
        "proportional formula should yield far less than the full position loss"
    )
