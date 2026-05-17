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
    """HTMX targets must point at #pane-action-outlet."""
    resp = client.get("/positions/pane?sym=AAPL")
    html = resp.text
    # All three buttons should reference the outlet selector.
    assert html.count("#pane-action-outlet") >= 3


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


def test_pane_action_basis_endpoint_returns_basis_form(client: TestClient) -> None:
    """GET /positions/pane/basis returns the set-basis form. With no
    seeded transfer-in lot the form may render empty or with a hint; just
    assert the endpoint responds 200 and returns a fragment (no <html>)."""
    resp = client.get("/positions/pane/basis?sym=NONEXIST")
    assert resp.status_code == 200
    html = resp.text
    assert "<html" not in html.lower()
