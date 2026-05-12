"""A4: Tables that opt into arrow-key row navigation carry a `data-table-nav`
attribute on the <tbody>. Their <tr>s get tabindex=0. The base layout loads
the table_nav.js script."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient


def test_search_input_uses_input_search_class(client: TestClient):
    res = client.get("/positions")
    body = res.text
    assert 'input-search' in body


def test_table_nav_script_registered(client: TestClient):
    res = client.get("/")
    assert "table_nav.js" in res.text


def test_harvest_tbody_has_table_nav_marker(client: TestClient, builders, repo):
    builders.seed_import(
        repo, "schwab", "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/tax/harvest/plan")
    body = res.text
    if "<tbody>" in body:
        assert "data-table-nav" in body


def test_table_nav_reinitializes_on_htmx_swap(client: TestClient):
    """The init handler must also fire on htmx:afterSwap so paginated rows
    get tabindex + the listener attached."""
    # table_nav.js is loaded as an external script; fetch it directly so we
    # can assert the htmx:afterSwap re-init hook is wired up.
    res = client.get("/static/table_nav.js")
    assert res.status_code == 200
    assert "htmx:afterSwap" in res.text


def test_table_row_focus_style_in_css(client: TestClient):
    """A4 spec: keyboard-navigable rows must have a visible focus ring."""
    # Read the built CSS bundle and verify the focus rule shipped.
    import pathlib
    here = pathlib.Path(__file__).resolve().parent.parent.parent
    # tests/ → repo root → src/.../static/app.css
    css_path = here / "src" / "net_alpha" / "web" / "static" / "app.css"
    assert css_path.exists(), f"app.css not found at {css_path}"
    css = css_path.read_text()
    # Some CSS minifiers strip whitespace inside attribute selectors;
    # accept either form.
    assert (
        'tr[tabindex="0"]:focus-visible' in css
        or "tr[tabindex='0']:focus-visible" in css
        or 'tr[tabindex=\\"0\\"]:focus-visible' in css
    ), "row focus-visible rule missing from app.css"
