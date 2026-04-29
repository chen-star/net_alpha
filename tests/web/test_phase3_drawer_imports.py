"""Phase 3 Imports drawer polish (§4.6, §6.2 I1/I2/I4)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_data_hygiene_renders_single_explanation_card(client: TestClient):
    """I1: one explanation card at top instead of per-row repetition."""
    resp = client.get("/imports/_legacy_page")
    html = resp.text
    if 'data-row="missing-basis"' not in html:
        return  # no fixture rows
    explanation_count = html.lower().count("until basis is set")
    assert explanation_count <= 1, f"explanation copy appears {explanation_count}× — expected ≤1"
    assert 'data-testid="hygiene-explanation"' in html


def test_data_hygiene_row_has_inline_save_form(client: TestClient):
    """I2: each missing-basis row has an inline form posting to
    /audit/set-basis?caller=drawer."""
    resp = client.get("/imports/_legacy_page")
    html = resp.text
    if 'data-row="missing-basis"' not in html:
        return
    assert 'hx-post="/audit/set-basis?caller=drawer"' in html


def test_drop_zone_carries_drag_preview_hooks(client: TestClient):
    """I4: the drop zone has dragover/dragleave handlers that show a preview
    of the incoming files."""
    resp = client.get("/imports/_legacy_page")
    html = resp.text
    assert 'data-testid="drop-zone-preview"' in html
    assert "/static/drop_zone.js" in html
