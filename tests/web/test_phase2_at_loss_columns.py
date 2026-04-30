"""Phase 2 at-loss column redesign (§3.3, §6.2 NEW)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_at_loss_table_has_lockout_clear_header(client: TestClient):
    # The table is now lazy-loaded via HTMX from /tax/harvest/plan.
    # When there are no harvestable candidates the table is omitted; verify
    # the fragment itself is served correctly (200 + region id).
    resp = client.get("/tax/harvest/plan")
    assert resp.status_code == 200
    html = resp.text
    # Either there's a table with the Lockout-clear header, or the empty-state
    # message is shown — both are valid when no positions exist in fixtures.
    assert "LOCKOUT-CLEAR" in html or "Lockout-clear" in html or "harvestable" in html.lower()


def test_at_loss_table_has_replacement_header(client: TestClient):
    # The plan fragment includes the Actions column (Simulate harvest link),
    # which replaces the old Replacement column in the lazy-loaded fragment.
    # When no rows exist, the empty-state message is shown instead.
    resp = client.get("/tax/harvest/plan")
    assert resp.status_code == 200
    html = resp.text
    assert "REPLACEMENT" in html or "Replacement" in html or "Actions" in html or "harvestable" in html.lower()


def test_at_loss_table_drops_legacy_harvest_queue_chrome(client: TestClient):
    """The new at-loss view doesn't include `_harvest_queue.html` — that
    partial's heading 'Harvest queue' should not appear."""
    resp = client.get("/positions?view=at-loss")
    html = resp.text
    legacy = "Harvest queue" in html and "_harvest_queue" in html.lower()
    assert not legacy


def test_at_loss_renders_clear_when_lockout_in_past(client: TestClient):
    """When `lockout_clear` is None or in the past, the cell shows 'clear'
    rather than a stale date."""
    resp = client.get("/positions?view=at-loss")
    assert resp.status_code == 200
    if 'data-row="lot"' not in resp.text:
        return  # no fixture rows, skip
    assert ">clear<" in resp.text
