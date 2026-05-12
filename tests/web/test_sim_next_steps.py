"""A1: Sim results render next-step CTAs that deep-link to existing routes."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient


def _seed_aapl_lot(repo, builders) -> None:
    """Seed an AAPL buy and materialize lots so the sim has holdings to sell from."""
    from net_alpha.engine.detector import detect_in_window

    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5), qty=10, cost=1000)],
    )
    win_start, win_end = date(2025, 12, 1), date(2026, 5, 1)
    res = detect_in_window(repo.trades_in_window(win_start, win_end), win_start, win_end, etf_pairs={})
    repo.replace_lots_in_window(win_start, win_end, res.lots)


def test_sim_sell_result_renders_next_steps(client: TestClient, builders, repo):
    _seed_aapl_lot(repo, builders)
    res = client.post(
        "/sim",
        data={
            "action": "sell",
            "ticker": "AAPL",
            "qty": "5",
            "price": "90",
            "account": "schwab/lt",
            "trade_date": "2026-04-01",
        },
    )
    assert res.status_code == 200
    body = res.text
    # All three CTAs render on a sell-at-a-loss.
    assert 'href="/positions?symbol=AAPL' in body
    assert 'href="/ticker/AAPL"' in body
    assert 'href="/tax/harvest/plan?pick=AAPL' in body
    # The strip has a stable wrapper for downstream assertions.
    assert 'data-testid="sim-next-steps"' in body


def test_sim_sell_at_gain_omits_harvest_cta(client: TestClient, builders, repo):
    _seed_aapl_lot(repo, builders)
    res = client.post(
        "/sim",
        data={
            "action": "sell",
            "ticker": "AAPL",
            "qty": "5",
            "price": "150",  # gain
            "account": "schwab/lt",
            "trade_date": "2026-04-01",
        },
    )
    assert res.status_code == 200
    body = res.text
    # No harvest CTA on a gain.
    assert "tax/harvest/plan?pick=" not in body
    # But the other two CTAs still render.
    assert 'href="/positions?symbol=AAPL' in body
    assert 'href="/ticker/AAPL"' in body


def test_sim_buy_result_renders_two_ctas(client: TestClient, builders, repo):
    _seed_aapl_lot(repo, builders)
    res = client.post(
        "/sim",
        data={
            "action": "buy",
            "ticker": "AAPL",
            "qty": "5",
            "price": "95",
            "account": "schwab/lt",
            "trade_date": "2026-04-01",
        },
    )
    assert res.status_code == 200
    body = res.text
    assert 'href="/positions?symbol=AAPL' in body
    assert 'href="/ticker/AAPL"' in body
    # No harvest CTA on a buy.
    assert "tax/harvest/plan?pick=" not in body
