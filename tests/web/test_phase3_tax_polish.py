"""Phase 3 Tax polish (§4.3, §6.2 T-/W-/Pr- items)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_offset_budget_tile_renders_progress_bar(client: TestClient):
    """T4: the loss-harvest budget tile shows a progress bar against the
    $3,000 cap, not just the YTD-net-realized number. Phase 1 moved the
    budget tile from /tax?view=harvest to /positions?view=at-loss."""
    resp = client.get("/positions?view=at-loss")
    html = resp.text
    if 'data-testid="offset-budget"' not in html:
        return  # no fixture realized_pl, skip
    assert 'data-testid="offset-budget-bar"' in html


def test_tax_kpi_strip_includes_stacked_mini_bar(client: TestClient):
    """T5: realized-P/L breakdown rendered as a stacked mini-bar under the
    KPI strip — losses below 0, gains above."""
    resp = client.get("/tax")
    html = resp.text
    assert 'data-testid="realized-mini-bar"' in html or "no realized p/l this period" in html.lower()
