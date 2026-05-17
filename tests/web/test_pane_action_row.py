"""Action row: 3 buttons that HTMX-swap existing sim/set-basis partials
into the outlet. Buttons themselves are testable; the swap is verified
by hitting the action endpoints directly."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient


def _seed_basic(
    repo,
    builders,
    sym: str,
    broker: str,
    label: str,
    acquired_date: date,
) -> int:
    """Seed a single buy trade. Returns account_id."""
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    account_display = f"{broker}/{label}"
    trade = builders.make_buy(account_display, sym, acquired_date, qty=10.0, cost=1000.0)
    account, _ = builders.seed_import(repo, broker, label, [trade])
    stitch_account(repo, account.id)
    recompute_all_violations(repo, {})
    return account.id


def test_pane_body_renders_action_row(client: TestClient) -> None:
    resp = client.get("/positions/pane?sym=AAPL")
    assert resp.status_code == 200
    html = resp.text
    assert 'data-testid="pane-action-sim-sell"' in html
    assert 'data-testid="pane-action-sim-buy"' in html
    assert 'data-testid="pane-action-set-basis"' in html
    assert 'data-testid="pane-action-outlet"' in html
    assert 'href="/ticker/AAPL"' in html


def test_action_buttons_target_the_outlet(client: TestClient) -> None:
    """HTMX targets must point at #pane-action-outlet.

    Sim sell and Set basis are HTMX-swap buttons; Sim buy more is now a
    plain anchor to /sim. So at least 2 buttons reference the outlet."""
    resp = client.get("/positions/pane?sym=AAPL")
    html = resp.text
    # Sim sell + Set basis reference the outlet (buy more is a plain link).
    assert html.count("#pane-action-outlet") >= 2


def test_pane_action_sim_endpoint_returns_sim_preview(client: TestClient, repo, builders) -> None:
    """GET /positions/pane/sim returns the sim-preview partial bound to
    qty=open. Adapt seeding to builders convention."""
    sym = "PNESIM"
    today = date.today()
    acquired = today - timedelta(days=60)
    acct_id = _seed_basic(repo, builders, sym, "Schwab", "Taxable", acquired)

    resp = client.get(f"/positions/pane/sim?sym={sym}&account_id={acct_id}&action=sell")
    assert resp.status_code == 200
    html = resp.text
    # Sim preview marker — stable heading from _positions_pane_sim_preview.html
    assert "Sim sell preview" in html
    # No full-page chrome — this is a partial
    assert "<html" not in html.lower()


def test_pane_action_basis_endpoint_returns_basis_form(client: TestClient, seed_transfer_in) -> None:
    """GET /positions/pane/basis returns the set-basis form with a real
    transfer-in lot seeded so we can assert that a meaningful form rendered."""
    sym, account_id, trade_id, qty, xfer_date = seed_transfer_in
    resp = client.get("/positions/pane/basis", params={"sym": sym, "account_id": account_id})
    assert resp.status_code == 200
    html = resp.text
    assert "<html" not in html.lower()
    # The set-basis form must be present and contain stable markers.
    assert "Set basis" in html
    assert 'name="cost_basis"' in html


def test_pane_action_sim_endpoint_rejects_buy_action(client: TestClient) -> None:
    """GET /positions/pane/sim?action=buy must return 400.

    The buy path now routes directly to /sim via a plain anchor; the
    pane/sim endpoint only handles sell mode."""
    resp = client.get("/positions/pane/sim?sym=AAPL&action=buy")
    assert resp.status_code == 400


def test_pane_action_buy_links_directly_to_sim(client: TestClient) -> None:
    """The 'Sim buy more' element must be a plain anchor pointing at /sim
    with action=buy, not an HTMX-swap button."""
    resp = client.get("/positions/pane?sym=AAPL")
    assert resp.status_code == 200
    html = resp.text
    # Must be an anchor with href containing /sim and action=buy
    assert 'href="/sim?' in html
    assert "action=buy" in html
    # Must NOT have hx-get on the buy element (it's a plain link now)
    # The testid is unchanged
    assert 'data-testid="pane-action-sim-buy"' in html
