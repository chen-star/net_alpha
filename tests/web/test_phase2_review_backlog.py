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
