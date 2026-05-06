"""Lot-strategy comparison panel on POST /sim with action=Sell.

Task 17 wires the engine.lot_selector into the Sim page: hitting Sell shows
a 5-row comparison (FIFO/LIFO/HIFO/Min Tax/Max Loss) with a recommendation
chip that prefers no-wash-sale picks then highest after-tax P&L.
"""

from __future__ import annotations

from datetime import date

import pytest


@pytest.fixture
def sim_setup(client, repo, builders):
    """Seed 100 SPY shares acquired 2024-01-15 at $80/share in one lot.

    Mirrors the engine-recompute pattern from test_sim_routes.py: import a
    Buy via the seed_import builder, then run the wash-sale detector to
    materialize the corresponding Lot.
    """
    from net_alpha.engine.detector import detect_in_window

    builders.seed_import(
        repo,
        "schwab",
        "personal",
        [
            builders.make_buy("schwab/personal", "SPY", date(2024, 1, 15), qty=100, cost=8000),
        ],
    )
    win_start, win_end = date(2023, 12, 1), date(2024, 3, 1)
    res = detect_in_window(
        repo.trades_in_window(win_start, win_end),
        win_start,
        win_end,
        etf_pairs={},
    )
    repo.replace_lots_in_window(win_start, win_end, res.lots)
    return client, repo


def test_sim_run_renders_lot_comparison_for_sell(sim_setup):
    client, _ = sim_setup
    resp = client.post(
        "/sim",
        data={
            "ticker": "SPY",
            "qty": "50",
            "price": "100",
            "action": "sell",
            "account": "schwab/personal",
        },
    )
    assert resp.status_code == 200
    body = resp.text
    # All five strategies appear in the comparison table.
    assert "Fifo" in body or "FIFO" in body
    assert "Lifo" in body or "LIFO" in body
    assert "Hifo" in body or "HIFO" in body
    assert "Min Tax" in body
    assert "Max Loss" in body
    # The recommendation chip is rendered.
    assert "Recommended" in body or 'data-recommended="true"' in body


def test_sim_run_buy_does_not_render_comparison(sim_setup):
    client, _ = sim_setup
    resp = client.post(
        "/sim",
        data={
            "ticker": "SPY",
            "qty": "50",
            "price": "100",
            "action": "buy",
        },
    )
    assert resp.status_code == 200
    # The comparison table is gated to Sell action — no "Min Tax" cell on Buy.
    assert "Min Tax" not in resp.text
    assert "Max Loss" not in resp.text


def test_sim_run_insufficient_lots_shows_message(sim_setup):
    client, _ = sim_setup
    resp = client.post(
        "/sim",
        data={
            "ticker": "SPY",
            "qty": "99999",
            "price": "100",
            "action": "sell",
            "account": "schwab/personal",
        },
    )
    assert resp.status_code == 200
    body = resp.text.lower()
    # Comparison should be skipped with a graceful message — not a crash.
    assert "available" in body or "unavailable" in body
