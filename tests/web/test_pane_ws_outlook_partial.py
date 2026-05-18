"""Partial wash-sale state in the pane outlook.

When selling all open shares would trigger a wash sale BUT selling fewer
shares (up to the gain-lot boundary) would NOT, the outlook shows:
  "Selling up to K of N today is safe; selling more triggers a wash sale."

This is reachable because simulate_sell uses FIFO lot consumption:
  - oldest lots (gain lots) are consumed first
  - is_loss = total realized < 0 across consumed lots
  - would_trigger fires only when is_loss is True AND a blocking buy exists

Scenario for partial state:
  - Gain lot: 50 shares bought 200d ago at $50/sh → GAIN at $100/sh
  - Loss lot: 50 shares bought 100d ago at $200/sh → LOSS at $100/sh
  - Blocking buy: 10 shares bought 5d ago (within ±30d of today)

  Selling ≤50 shares (FIFO: only gain lot consumed) → realized >= 0 → clean.
  Selling 51+ shares → loss lot consumed → realized < 0 → triggers wash sale.

  Binary search finds safe_qty = 50.

Scenario for trigger (no partial reachable):
  - All lots are loss lots (blocking buy covers full position).
  - Even selling 1 share triggers (is_loss is True for any qty > 0).
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient


def _seed_price(engine, sym: str, price: float) -> None:
    """Inject a cached quote so the pane has a real last_price."""
    import datetime as _dt
    from decimal import Decimal

    from net_alpha.pricing.cache import PriceCache
    from net_alpha.pricing.provider import Quote

    cache = PriceCache(engine)
    cache.put_many(
        [Quote(symbol=sym, price=Decimal(str(price)), as_of=_dt.datetime.now(_dt.UTC), source="test")]
    )


def test_ws_outlook_partial_state_gain_then_loss_lot(
    client: TestClient, repo, builders, engine
) -> None:
    """Partial state: gain lot (FIFO first) + loss lot + blocking buy.

    FIFO consumption reaches a loss only when selling beyond the gain-lot
    boundary, so selling ≤ gain-lot qty is clean; selling more triggers.

    Position:
      Lot A: 50 sh @ $50/sh (200d ago) — GAIN at $100
      Lot B: 50 sh @ $200/sh (100d ago) — LOSS at $100
      Blocking buy: 10 sh (5d ago)

    Selling 1–50 sh: only Lot A consumed → realized > 0 → clean.
    Selling 51–100 sh: Lot B consumed → realized < 0 → triggers.
    Expected safe_qty = 50.
    """
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    sym = "PARTSELL"
    today = date.today()
    display = "Schwab/Taxable"

    # Lot A: gain lot — oldest, consumed first by FIFO
    buy_gain = builders.make_buy(
        display, sym, today - timedelta(days=200), qty=50.0, cost=2_500.0  # $50/sh
    )
    # Lot B: loss lot — more recent, consumed second
    buy_loss = builders.make_buy(
        display, sym, today - timedelta(days=100), qty=50.0, cost=10_000.0  # $200/sh
    )
    # Blocking buy in ±30d window — triggers wash sale when loss lot consumed
    buy_blocking = builders.make_buy(
        display, sym, today - timedelta(days=5), qty=10.0, cost=900.0
    )

    acct, _ = builders.seed_import(repo, "Schwab", "Taxable", [buy_gain, buy_loss, buy_blocking])
    stitch_account(repo, acct.id)
    recompute_all_violations(repo, {})

    # Price $100/sh: Lot A at gain ($50 basis), Lot B at loss ($200 basis)
    _seed_price(engine, sym, 100.0)

    resp = client.get(f"/positions/pane?sym={sym}&account_id={acct.id}")
    assert resp.status_code == 200
    html = resp.text

    # Must be partial state (not trigger), because selling ≤50 sh is safe
    assert 'data-state="partial"' in html, (
        f"expected partial state, got state from html: "
        f"{html[html.find('data-state'):html.find('data-state')+30] if 'data-state' in html else 'NOT FOUND'}"
    )
    assert "safe" in html.lower(), "expected 'safe' in partial-state message"
    assert "triggers a wash sale" in html.lower(), "expected 'triggers a wash sale' in partial message"

    # The safe qty should be 50 (all gain-lot shares)
    assert "50" in html, "expected safe_qty=50 in partial message"


def test_ws_outlook_trigger_state_when_all_lots_are_losses(
    client: TestClient, repo, builders, engine
) -> None:
    """When all lots are loss lots, even selling 1 share triggers — no partial.

    Position:
      Lot A: 100 sh @ $200/sh (100d ago) — LOSS at $100
      Blocking buy: 100 sh (5d ago) — full coverage

    Selling any qty: realized < 0 → triggers immediately.
    Bisection finds no safe qty → falls back to trigger state.
    """
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    sym = "FULLTRIG"
    today = date.today()
    display = "Schwab/Taxable"

    buy_main = builders.make_buy(
        display, sym, today - timedelta(days=100), qty=100.0, cost=20_000.0  # $200/sh
    )
    # Full replacement buy — 100 sh within ±30d
    buy_blocking = builders.make_buy(
        display, sym, today - timedelta(days=5), qty=100.0, cost=15_000.0
    )

    acct, _ = builders.seed_import(repo, "Schwab", "Taxable", [buy_main, buy_blocking])
    stitch_account(repo, acct.id)
    recompute_all_violations(repo, {})

    # Price $100/sh — below $200/sh basis on all lots → always a loss
    _seed_price(engine, sym, 100.0)

    resp = client.get(f"/positions/pane?sym={sym}&account_id={acct.id}")
    assert resp.status_code == 200
    html = resp.text

    # Must be trigger (not partial), because even selling 1 share triggers
    assert 'data-state="trigger"' in html, (
        f"expected trigger state, got: "
        f"{html[html.find('data-state'):html.find('data-state')+30] if 'data-state' in html else 'NOT FOUND'}"
    )
    assert "wash sale" in html.lower()
    assert "disallowed" in html.lower()
