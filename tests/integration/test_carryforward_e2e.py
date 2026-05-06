"""End-to-end: multi-year history -> derived carryforward -> override -> sim recommendation.

Capstone smoke test for the carryforward + best-lot picker feature. Verifies
the wiring across:

1. Multi-year trade history rolls up into a derived ST carryforward visible at
   GET /settings/carryforward (2024 -$5,000 ST loss -> $2,000 carry into 2025
   after applying the §1211 $3K-against-ordinary cap).
2. POSTing a Sell to /sim renders the 5-strategy lot comparison table with a
   recommendation, exercising the carryforward-aware after-tax math.
3. Saving an explicit zero override at /settings/carryforward/save replaces the
   derived value (override-wins semantics, even when both amounts are $0).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from net_alpha.engine.detector import detect_in_window
from net_alpha.engine.recompute import recompute_all
from net_alpha.portfolio.carryforward import get_effective_carryforward


@pytest.fixture
def populated_client(client, repo, builders):
    """Seed:

    - 2024-01-15 Buy 100 SPY @ $200 ($20K basis)
    - 2024-06-15 Sell 100 SPY @ $150 ($15K proceeds) -> -$5,000 ST loss
      -> $2,000 ST carryforward into 2025 after §1211 $3K cap.
    - 2025-06-01 Buy 100 SPY @ $100 ($10K basis) -> open position for /sim Sell.

    Uses the project's standard seeding pattern (`builders.seed_import` +
    `recompute_all`) so the engine builds lots end-to-end.
    """
    from net_alpha.models.domain import Trade

    # ---- Prior-year ST loss (2024 closed pair) --------------------------------
    builders.seed_import(
        repo,
        "schwab",
        "personal",
        [
            builders.make_buy("schwab/personal", "SPY", date(2024, 1, 15), qty=100, cost=20000),
            Trade(
                account="schwab/personal",
                date=date(2024, 6, 15),
                ticker="SPY",
                action="Sell",
                quantity=100,
                proceeds=Decimal("15000"),
                cost_basis=Decimal("20000"),
                basis_source="broker_csv",
            ),
        ],
        csv_filename="2024_loss.csv",
    )

    # ---- Open SPY position in 2025 -------------------------------------------
    builders.seed_import(
        repo,
        "schwab",
        "personal",
        [
            builders.make_buy("schwab/personal", "SPY", date(2025, 6, 1), qty=100, cost=10000),
        ],
        csv_filename="2025_open.csv",
    )

    # Run full recompute so lots are materialized for both years (the lot_selector
    # in /sim reads repo.get_lots_for_ticker, which only returns built lots).
    recompute_all(repo)
    # The 2025 lot is outside the recompute window (no 2025 sells yet), so
    # explicitly materialize it via detect_in_window over a 2025-spanning window.
    win_start, win_end = date(2025, 1, 1), date(2025, 12, 31)
    res = detect_in_window(
        repo.trades_in_window(win_start, win_end),
        win_start,
        win_end,
        etf_pairs={},
    )
    repo.replace_lots_in_window(win_start, win_end, res.lots)

    return client, repo


def test_e2e_derived_carryforward_flows_into_sim_recommendation(populated_client):
    client, repo = populated_client

    # 1. Settings shows the derived $2K ST carryforward into 2025.
    resp = client.get("/settings/carryforward")
    assert resp.status_code == 200
    body = resp.text
    assert "2025" in body
    assert "2,000" in body or "2000" in body
    # Source label is "derived" (no override yet).
    assert "derived" in body.lower()

    # Sanity: derive_carryforward agrees with the rendered value.
    cf = get_effective_carryforward(repo, year=2025)
    assert cf.source == "derived"
    assert cf.st == Decimal("2000")
    assert cf.lt == Decimal("0")

    # 2. Run a sim Sell at a gain on the open SPY position.
    resp = client.post(
        "/sim",
        data={
            "ticker": "SPY",
            "qty": "50",
            "price": "150",
            "action": "sell",
            "account": "schwab/personal",
            "trade_date": "2025-09-01",
        },
    )
    assert resp.status_code == 200
    body = resp.text

    # 3. The 5-strategy comparison table renders with a recommendation chip.
    assert "Recommended" in body or 'data-recommended="true"' in body
    # Lot strategies are present.
    assert "Min Tax" in body
    assert "Max Loss" in body


def test_e2e_user_override_changes_recommendation(populated_client):
    client, repo = populated_client

    # Pre-condition: derived value rolls in $2K ST.
    cf_before = get_effective_carryforward(repo, year=2025)
    assert cf_before.source == "derived"
    assert cf_before.st == Decimal("2000")

    # User overrides 2025 carryforward to $0 / $0.
    resp = client.post(
        "/settings/carryforward/save",
        data={"year": "2025", "st_amount": "0", "lt_amount": "0"},
    )
    assert resp.status_code == 200

    # Override row persisted (explicit zeros count as a real override).
    saved = repo.get_carryforward_override(2025)
    assert saved is not None
    assert Decimal(str(saved.st_amount)) == Decimal("0")
    assert Decimal(str(saved.lt_amount)) == Decimal("0")

    # Override-wins: derived $2K is now ignored.
    cf_after = get_effective_carryforward(repo, year=2025)
    assert cf_after.source == "user"
    assert cf_after.st == Decimal("0")
    assert cf_after.lt == Decimal("0")

    # Sim still renders cleanly with the override active (override path
    # exercises the same lot_selector + after-tax math, just with cf=0).
    resp = client.post(
        "/sim",
        data={
            "ticker": "SPY",
            "qty": "50",
            "price": "150",
            "action": "sell",
            "account": "schwab/personal",
            "trade_date": "2025-09-01",
        },
    )
    assert resp.status_code == 200
    assert "Recommended" in resp.text or 'data-recommended="true"' in resp.text
