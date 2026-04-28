"""Phase 1 review-backlog cleanup (Phase 2 Section A)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_empty_state_cta_targets_settings_imports(client: TestClient):
    """The empty-state CTA links to /settings/imports directly so users
    don't pay an extra 301 hop. The /imports redirect still exists for
    bookmarks (Phase 1 A3)."""
    resp = client.get("/")
    html = resp.text
    if 'href="/settings/imports"' not in html and 'href="/imports"' not in html:
        # Account-set users don't see the empty state — skip
        return
    # If the CTA is rendered, it should be the new URL
    assert 'href="/settings/imports"' in html


def test_legacy_imports_page_does_not_highlight_overview(client: TestClient):
    """The legacy /imports/_legacy_page is HTMX-only; if a human stumbles
    onto it the nav shouldn't lie about which page they're on."""
    resp = client.get("/imports/_legacy_page")
    assert resp.status_code == 200
    html = resp.text
    # Find the Overview anchor; it should NOT have the 'active' class.
    overview_idx = html.find(">Overview<")
    if overview_idx < 0:
        return  # nav not rendered (e.g. no accounts); skip
    anchor_start = html.rfind("<a", 0, overview_idx)
    anchor_html = html[anchor_start:overview_idx]
    assert "active" not in anchor_html, (
        f"Overview link is highlighted on /imports/_legacy_page: {anchor_html}"
    )


def test_drawer_placeholder_tabs_say_coming_soon(client: TestClient):
    """The Profile / ETF pairs / About tabs use 'Coming soon' rather than a
    specific phase number. Specific numbers drift; vague is honest."""
    resp = client.get("/")
    html = resp.text
    drawer_idx = html.find('id="settings-drawer-root"')
    if drawer_idx < 0:
        return  # drawer not mounted (no accounts state); skip
    drawer_html = html[drawer_idx:drawer_idx + 12_000]
    assert "Coming soon" in drawer_html
    assert "Phase 2" not in drawer_html
    assert "Phase 3" not in drawer_html
