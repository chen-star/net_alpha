"""Task 10: Badge HTMX fragment endpoint (Overview).

The Overview page shell loads the verify badge lazily via HTMX. The badge
endpoint runs the OV-* / AL-* invariants over the same pure-function
inputs (`compute_kpis`, `build_allocation`) the renderer fragments use,
so renderer and verifier agree by construction.
"""

from __future__ import annotations


def test_overview_shell_includes_badge_placeholder(client):
    """The Overview shell must HTMX-load the badge fragment."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'hx-get="/verify/badge?page=overview"' in resp.text


def test_badge_fragment_endpoint_returns_status(client):
    """The badge fragment endpoint renders the partial with a status attr."""
    resp = client.get("/verify/badge?page=overview")
    assert resp.status_code == 200
    assert "data-verify-badge" in resp.text
    # Empty DB → invariants vacuously pass.
    assert 'data-verify-status="ok"' in resp.text


def test_badge_fragment_rejects_unknown_page(client):
    resp = client.get("/verify/badge?page=fictional")
    assert resp.status_code == 400
