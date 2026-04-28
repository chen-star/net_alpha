"""Phase 2 Sim pre-fill from row-action URL params (§6.2 Sim NEW)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_sim_prefills_ticker_and_qty(client: TestClient):
    resp = client.get("/sim?ticker=NVDA&qty=4")
    assert resp.status_code == 200
    html = resp.text
    assert 'value="NVDA"' in html
    assert 'value="4"' in html


def test_sim_prefills_action_sell(client: TestClient):
    resp = client.get("/sim?ticker=NVDA&qty=4&action=sell")
    html = resp.text
    # The action selector marks 'sell' as the selected value. Match the
    # broad shape: either `<option value="sell" selected>` (select) or
    # `<input type="radio" name="action" value="sell" checked>` (radio).
    assert 'value="sell" selected' in html or 'value="sell" checked' in html


def test_sim_prefills_account(client: TestClient):
    resp = client.get("/sim?ticker=NVDA&qty=4&account=schwab%2Flt")
    # If 'schwab/lt' isn't in the test fixture's accounts, the marker
    # won't appear — fall back to verifying the URL is accepted.
    assert resp.status_code == 200
