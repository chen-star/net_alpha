"""Phase 3 Sim validation + recents (§6.2 S2, S3)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_sim_post_sell_without_account_returns_inline_error(client: TestClient):
    """S3: action=Sell with empty account yields an inline error fragment,
    not a full-page swap (review C3)."""
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
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200
    html = resp.text
    # Error message present
    assert "account is required" in html.lower() or "required for sell" in html.lower()
    # Response is a partial (no full HTML document)
    assert "<html" not in html.lower(), "error response is a full page, not a partial"
    assert "<!DOCTYPE" not in html, "error response is a full page, not a partial"
    # Bytes are small (under 2KB)
    assert len(html) < 2000, f"error response is {len(html)} bytes — should be a small fragment"
    # OOB swap directive is present
    assert "hx-swap-oob" in html


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
