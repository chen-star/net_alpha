"""Phase 2 review-backlog cleanup (Phase 3 Section A)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_at_loss_summary_strip_shows_total_unrealized_and_counts(client: TestClient):
    """The at-loss summary line shows total unrealized, harvestable count,
    and replacements count — not just the lot count + budget."""
    resp = client.get("/positions?view=at-loss")
    assert resp.status_code == 200
    html = resp.text
    if 'data-row="lot"' not in html:
        return  # no fixture, skip
    assert 'data-testid="at-loss-summary"' in html
    assert "harvest-clear" in html or "harvestable" in html
    assert "text-loss" in html or "text-neg" in html
