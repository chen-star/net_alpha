"""Phase 1 positions tabs (§3.3 of UI/UX redesign spec)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_positions_page_has_five_tab_links(client: TestClient):
    resp = client.get("/positions")
    html = resp.text
    for label in ("All", "Stocks", "Options", "At a loss", "Closed"):
        assert f">{label}<" in html, f"missing tab: {label}"


def test_default_tab_is_all_when_no_view_param(client: TestClient):
    resp = client.get("/positions")
    html = resp.text
    all_idx = html.find(">All<")
    assert all_idx > 0
    anchor_start = html.rfind("<a", 0, all_idx)
    anchor_html = html[anchor_start:all_idx]
    assert "tab--active" in anchor_html


def test_at_loss_tab_links_to_view_at_loss(client: TestClient):
    resp = client.get("/positions")
    # href includes view=at-loss; may also carry &period= state
    assert 'href="/positions?view=at-loss' in resp.text


def test_view_at_loss_marks_at_loss_tab_active(client: TestClient):
    resp = client.get("/positions?view=at-loss")
    html = resp.text
    at_loss_idx = html.find(">At a loss<")
    assert at_loss_idx > 0
    anchor_start = html.rfind("<a", 0, at_loss_idx)
    anchor_html = html[anchor_start:at_loss_idx]
    assert "tab--active" in anchor_html


def test_at_loss_view_renders_harvest_queue_content(client: TestClient):
    """`/positions?view=at-loss` shows the same harvest queue table that
    `/tax?view=harvest` used to render before the redirect."""
    resp = client.get("/positions?view=at-loss")
    html = resp.text
    assert resp.status_code == 200
    # Harvest queue uses literal section title 'Harvest queue'. If the
    # heading was renamed, update assertion.
    assert "Harvest queue" in html or "harvest queue" in html.lower()


def test_view_all_renders_existing_positions_table(client: TestClient):
    """`/positions?view=all` renders the same positions panel that users had
    on /holdings pre-rename (HTMX-loaded; server side emits the trigger div)."""
    resp = client.get("/positions?view=all")
    html = resp.text
    assert resp.status_code == 200
    # The positions content is loaded via HTMX; the server renders either the
    # trigger div (when imports exist) or the empty-state partial (no data).
    assert "/portfolio/positions" in html or "no data" in html.lower() or "import" in html.lower()


def test_tax_page_no_longer_has_harvest_tab(client: TestClient):
    resp = client.get("/tax")
    html = resp.text
    assert ">Harvest<" not in html, "Tax page still has Harvest tab"
    assert "Wash sales" in html
    assert "Projection" in html
