"""Pane header partial: extracted from inline body in Task 1 of the
positions-pane-cockpit plan. This test pins the new partial's contract:
it must render the same field set the inline header did, and it must be
included by `_positions_pane_body.html`."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_pane_body_includes_header_partial(client: TestClient) -> None:
    """The pane body must include the new header partial (we can't grep
    for the include directive in rendered HTML, so we instead assert the
    body still contains the symbol — a proxy for the partial running
    correctly — and that the dedicated header testid is present."""
    resp = client.get("/positions/pane?sym=AAPL")
    assert resp.status_code == 200
    html = resp.text
    assert "AAPL" in html
    assert 'data-testid="pane-header"' in html


def test_pane_header_partial_present_in_template_tree() -> None:
    """Build-time guarantee: the partial file exists on disk so future
    changes that delete it surface in CI."""
    from pathlib import Path
    p = Path(__file__).parents[2] / "src/net_alpha/web/templates/_positions_pane_header.html"
    assert p.exists(), f"missing partial: {p}"
