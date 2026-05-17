"""Composition smoke test — every sub-block from the cockpit spec must be
present in a single pane response when the underlying data is rich enough
to surface each section.

Catches the "I added a new partial but forgot to include it in the body"
regression and the inverse — "I removed a partial but forgot to remove
its test." Should fail loudly on either.
"""

from __future__ import annotations

import datetime as dt
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient


def test_pane_renders_all_six_blocks(client: TestClient, repo, builders, engine) -> None:
    """Composition smoke test: seed a richly-populated position and assert
    every sub-block's testid is present in a single pane render.

    Scenario:
      - Symbol: ALLIN (unique name, no collision with other tests)
      - Lot 1: 100 shares acquired 280 days ago (86d to LT — clock fires)
      - Lot 2: 50 shares acquired 5 days ago (replacement buy triggers wash-sale)
      - Price: seeded at $50/share, below Lot 1's basis ($100) → at-loss state
      - This surfaces:
        1. pane-header (symbol display)
        2. st-lt-clock (Lot 1 is 86d to LT)
        3. pane-action-sim-sell + pane-action-outlet (action row with outlet)
        4. lot-row (two open lots in the ladder)
        5. ws-outlook (trigger state — Lot 1 would lose money, Lot 2 blocks it)
        6. recent-row (recent trades)
    """
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account
    from net_alpha.pricing.cache import PriceCache
    from net_alpha.pricing.provider import Quote

    sym = "ALLIN"
    today = date.today()
    account_display = "Schwab/Taxable"

    # Lot 1: 100 shares acquired 280 days ago at $100/share → $10,000 cost
    # With today's price at $50, this is a $5,000 loss.
    # 280 days old leaves 86 days to LT (366d cutoff), so clock should fire.
    lot1_date = today - timedelta(days=280)
    lot1 = builders.make_buy(account_display, sym, lot1_date, qty=100.0, cost=10000.0)

    # Lot 2: 50 shares acquired 5 days ago at $80/share → $4,000 cost
    # This is the "replacement buy" within ±30 days that triggers wash sale.
    lot2_date = today - timedelta(days=5)
    lot2 = builders.make_buy(account_display, sym, lot2_date, qty=50.0, cost=4000.0)

    # Seed both trades to the DB via builders.seed_import.
    account, _ = builders.seed_import(repo, "Schwab", "Taxable", [lot1, lot2])

    # Stitch the account to ensure it exists in the DB.
    stitch_account(repo, account.id)

    # Recompute wash-sale violations (creates WashSaleViolation records if applicable).
    recompute_all_violations(repo, {})

    # Seed a quote at $50/share (below both lot bases) so:
    #  - last_price is non-None (drives unrealized P&L computation)
    #  - Lot 1 is at-loss (triggers wash-sale-outlook risk assessment)
    cache = PriceCache(engine)
    cache.put_many(
        [
            Quote(
                symbol=sym,
                price=Decimal("50.0"),
                as_of=dt.datetime.now(dt.UTC),
                source="test",
            )
        ]
    )

    # Fetch the pane for ALLIN in the Schwab/Taxable account.
    resp = client.get(f"/positions/pane?sym={sym}&account_id={account.id}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    html = resp.text

    # All six sub-blocks must be present (else the composition is broken).
    assert 'data-testid="pane-header"' in html, "pane-header missing"
    assert 'data-testid="st-lt-clock"' in html, "st-lt-clock missing (Lot 1 should be 86d to LT)"
    assert 'data-testid="pane-action-sim-sell"' in html, "pane-action-sim-sell missing"
    assert 'data-testid="pane-action-outlet"' in html, "pane-action-outlet missing"
    assert 'data-testid="lot-row"' in html, "lot-row missing (should have ≥1 lot)"
    assert 'data-testid="ws-outlook"' in html, "ws-outlook missing (should have wash-sale trigger)"
    assert 'data-testid="recent-row"' in html, "recent-row missing (should have recent trades)"
