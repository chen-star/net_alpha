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
    assert "active" not in anchor_html, f"Overview link is highlighted on /imports/_legacy_page: {anchor_html}"


def test_drawer_tabs_have_real_content(client: TestClient):
    """Profile / ETF pairs / About tabs ship real content (not placeholders).
    Specific phase numbers drift; this just sanity-checks each tab rendered."""
    resp = client.get("/")
    html = resp.text
    drawer_idx = html.find('id="settings-drawer-root"')
    if drawer_idx < 0:
        return  # drawer not mounted (no accounts state); skip
    drawer_html = html[drawer_idx:]
    # About tab — version label + privacy heading
    assert "Version" in drawer_html
    assert "Privacy" in drawer_html
    # ETF pairs tab — bundled SP500 group is always present
    assert "SPY" in drawer_html and "VOO" in drawer_html
    # Profile tab — Conservative/Active/Options choices are rendered
    assert "Conservative" in drawer_html
    assert "Options" in drawer_html
    # No leftover placeholder copy
    assert "Coming soon" not in drawer_html
    assert "Phase 2" not in drawer_html
    assert "Phase 3" not in drawer_html


def test_settings_entry_has_polite_main_copy(client: TestClient):
    """If the user closes the drawer on /settings/imports they see at minimum
    a polite explanation, not an empty <main>."""
    resp = client.get("/settings/imports")
    assert resp.status_code == 200
    html = resp.text
    # Look for the polite hint copy.
    assert "Settings open in the panel" in html or "panel on the right" in html
