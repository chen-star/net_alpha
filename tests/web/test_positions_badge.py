"""Task 11: Wire badge fragment into /positions shell.

The badge endpoint already supports ``page=positions`` from Task 10. This
test pins the Positions shell to load the badge lazily and confirms the
XP-1 cross-page check is reachable.
"""

from __future__ import annotations


def test_positions_shell_omits_page_level_badge(client):
    """The page-level verify badge was removed from /positions (and the
    Overview page) — the topbar "Data check: …" pill in base.html now
    surfaces the same status site-wide, and the duplicate chip was
    confusing users. The badge endpoint still exists for callers that
    want it; just the page-level slot in this template is gone."""
    resp = client.get("/positions")
    assert resp.status_code == 200
    assert 'hx-get="/verify/badge?page=positions"' not in resp.text
    assert "verify-badge-slot" not in resp.text


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
