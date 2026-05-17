"""Sticky-open: positions_pane.js loads on the positions page and
listens for filter-change signals so it can close the pane when the
currently-open symbol is filtered out."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_positions_pane_js_is_loaded_on_positions_page(client: TestClient) -> None:
    resp = client.get("/positions")
    html = resp.text
    assert "/static/positions_pane.js" in html


def test_positions_pane_js_file_exists() -> None:
    p = Path(__file__).parents[2] / "src/net_alpha/web/static/positions_pane.js"
    assert p.exists(), f"missing script: {p}"


def test_positions_pane_js_wires_htmx_swap_listener() -> None:
    """The script must listen for htmx:afterSwap on (or scoped to)
    #holdings-positions so it re-checks visibility after every HTMX swap
    that re-renders the holdings table."""
    src = Path(__file__).parents[2] / "src/net_alpha/web/static/positions_pane.js"
    text = src.read_text()
    assert "htmx:afterSwap" in text
    assert "holdings-positions" in text


def test_positions_pane_js_wraps_symbol_filter_hook() -> None:
    """The script must wrap window.__applyPositionsSymbolFilter (or its
    actual name found in positions_search.js) so each apply re-checks."""
    src = Path(__file__).parents[2] / "src/net_alpha/web/static/positions_pane.js"
    text = src.read_text()
    # Either it wraps the function or it listens for an event the search
    # script dispatches. Accept either form, but it must reference the
    # symbol-search seam by name.
    assert "__applyPositionsSymbolFilter" in text or "positions:filter" in text


def test_positions_pane_js_uses_data_row_position_attribute() -> None:
    """Sanity assert: the visibility check reads from rows tagged
    data-row="position" (matching the actual template attribute)."""
    src = Path(__file__).parents[2] / "src/net_alpha/web/static/positions_pane.js"
    text = src.read_text()
    assert 'data-row="position"' in text or "data-row='position'" in text or 'tr[data-row=' in text


def test_positions_pane_js_uses_alpine_v3_api_not_v2() -> None:
    """The pane script must use window.Alpine.$data(el) (v3), not
    el.__x.$data (v2 — broken with the project's Alpine 3.14.1)."""
    src = Path(__file__).parents[2] / "src/net_alpha/web/static/positions_pane.js"
    text = src.read_text()
    assert "Alpine.$data" in text, "must use Alpine v3 API"
    assert "__x.$data" not in text, "Alpine v2 internal __x.$data does not exist in v3"
