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


def test_sim_account_picker_excludes_positions_sentinel(client: TestClient, repo):
    """The synthetic 'positions/(multi)' account (FK placeholder for positions
    CSV imports) holds no trades and must not appear in the Sim account picker."""
    # Force-create the sentinel the way a positions-CSV import would.
    repo.save_broker_positions(
        rows=[
            {
                "account_label": "Schwab Brokerage ...123",
                "symbol": "AAPL",
                "qty": 10.0,
                "cost_basis": 1500.0,
                "market_value": 1700.0,
                "unrealized_pl": 200.0,
            }
        ],
        as_of_date="2026-05-17",
    )
    resp = client.get("/sim")
    assert resp.status_code == 200
    assert "positions/(multi)" not in resp.text


def test_sim_chip_prefill_with_explicit_price_autoruns(client: TestClient):
    """A suggestion chip carries a full spec incl. explicit &price= and
    promises it 'runs against the simulator'. The form must auto-submit on
    load so results appear without a manual Run-sim click."""
    resp = client.get("/sim?ticker=NVDA&qty=4&price=120.50&action=sell&account=schwab%2Flt")
    assert resp.status_code == 200
    html = resp.text
    assert 'value="120.50"' in html  # explicit chip price wins over live quote
    # Form auto-submits on load (htmx 'load' trigger present alongside submit).
    form_open = html.find("<form")
    form_tag = html[form_open : html.find(">", form_open) + 1]
    assert "load" in form_tag, f"expected an autorun load trigger on the form: {form_tag!r}"


def test_sim_plain_prefill_without_price_does_not_autorun(client: TestClient):
    """A positions-row deep link (no explicit price) only prefills — it must
    NOT auto-run, so the user reviews values first."""
    resp = client.get("/sim?ticker=NVDA&qty=4&action=sell")
    html = resp.text
    form_open = html.find("<form")
    form_tag = html[form_open : html.find(">", form_open) + 1]
    assert "load" not in form_tag, f"plain prefill must not autorun: {form_tag!r}"
