"""Task 11: Wire badge fragment into /positions shell.

The badge endpoint already supports ``page=positions`` from Task 10. This
test pins the Positions shell to load the badge lazily and confirms the
XP-1 cross-page check is reachable.
"""

from __future__ import annotations


def test_positions_shell_includes_badge_placeholder(client):
    resp = client.get("/positions")
    assert resp.status_code == 200
    assert 'hx-get="/verify/badge?page=positions"' in resp.text


def test_positions_badge_fragment_renders(client):
    resp = client.get("/verify/badge?page=positions")
    assert resp.status_code == 200
    assert "data-verify-badge" in resp.text


def test_xp1_passes_after_overview_visit(client):
    """After /verify/badge?page=overview runs, XP-1 should be checkable on positions."""
    # First request seeds the OverviewTotalCache.
    client.get("/verify/badge?page=overview")
    # Positions badge fragment should now have XP-1 either pass (cache hit, equal sums)
    # or skip (cache miss). On empty DB both totals are 0.0, so XP-1 passes.
    resp = client.get("/verify/badge?page=positions")
    assert 'data-verify-status="ok"' in resp.text
