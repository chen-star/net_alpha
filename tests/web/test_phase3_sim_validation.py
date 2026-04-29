"""Phase 3 Sim validation + recents (§6.2 S2, S3)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_sim_post_sell_without_account_returns_inline_error(client: TestClient):
    """S3: action=Sell with empty account yields an inline error, not a 500."""
    resp = client.post(
        "/sim",
        data={
            "action": "sell",
            "ticker": "NVDA",
            "qty": "1",
            "price": "100",
            "trade_date": "2026-04-28",
            # NO account
        },
    )
    assert resp.status_code in (200, 400, 422)
    assert "account is required" in resp.text.lower() or "required for sell" in resp.text.lower()


def test_sim_post_buy_without_account_succeeds(client: TestClient):
    """Buy doesn't require account (an account-less buy is the contributed-cash flow).
    Verify the inline error is gated to action=Sell."""
    resp = client.post(
        "/sim",
        data={
            "action": "buy",
            "ticker": "NVDA",
            "qty": "1",
            "price": "100",
            "trade_date": "2026-04-28",
        },
    )
    assert resp.status_code == 200


def test_sim_page_mounts_recents_panel(client: TestClient):
    """S2: Sim page has a 'Recent sims · this session' panel powered by
    Alpine + localStorage."""
    resp = client.get("/sim")
    html = resp.text
    assert 'data-testid="sim-recents"' in html
    assert "Recent sims" in html
