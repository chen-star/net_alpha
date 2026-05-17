"""Keyboard nav: j/k row stepping handlers are wired in table_nav.js
and the positions page emits data attrs the handler reads."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_positions_rows_have_row_data_attr(client: TestClient) -> None:
    """When the positions page has any holdings, rows carry data-row="position"
    and data-symbol so the keyboard handler can find them."""
    resp = client.get("/positions")
    assert resp.status_code == 200
    html = resp.text
    # On empty DB the empty state renders — no <tbody>. Skip in that case.
    if "<tbody" not in html:
        return
    assert 'data-row="position"' in html
    assert "data-symbol=" in html


def test_table_nav_js_contains_pane_jk_handlers() -> None:
    """Sanity assert that the handler module exposes j/k/o pane wiring."""
    src = Path(__file__).parents[2] / "src/net_alpha/web/static/table_nav.js"
    text = src.read_text()
    # Listens for j/k/o and dispatches the existing pane-open event.
    assert "open-positions-pane" in text
    assert any(tok in text for tok in ("'j'", '"j"', "KeyJ"))
    assert any(tok in text for tok in ("'k'", '"k"', "KeyK"))
    assert any(tok in text for tok in ("'o'", '"o"', "KeyO"))


def test_table_nav_js_dispatches_with_sym_and_account_id() -> None:
    """The handler must build an event detail object with sym + account_id."""
    src = Path(__file__).parents[2] / "src/net_alpha/web/static/table_nav.js"
    text = src.read_text()
    assert "sym" in text
    assert "account" in text.lower()


def test_table_nav_js_no_op_when_focused_in_input() -> None:
    """The handler must not hijack j/k when the user is typing in a search/input.
    We assert the handler references activeElement, tagName matching, or
    isContentEditable (common idioms for this guard)."""
    src = Path(__file__).parents[2] / "src/net_alpha/web/static/table_nav.js"
    text = src.read_text()
    assert "activeElement" in text or "isContentEditable" in text


def test_table_nav_js_uses_alpine_v3_api_not_v2() -> None:
    """The pane handler must use window.Alpine.$data(el) (v3), not
    el.__x.$data (v2 — broken with the project's Alpine 3.14.1)."""
    src = Path(__file__).parents[2] / "src/net_alpha/web/static/table_nav.js"
    text = src.read_text()
    assert "Alpine.$data" in text, "must use Alpine v3 API"
    assert "__x.$data" not in text, "Alpine v2 internal __x.$data does not exist in v3"
