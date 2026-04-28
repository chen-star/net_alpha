"""Phase 1 settings drawer tabs (§3.6 of UI/UX redesign spec)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_drawer_has_five_tab_buttons(client: TestClient):
    resp = client.get("/")
    html = resp.text
    for label in ("Imports", "Profile", "Density", "ETF pairs", "About"):
        assert f">{label}<" in html, f"missing tab: {label}"


def test_drawer_close_button_present(client: TestClient):
    resp = client.get("/")
    assert 'data-testid="settings-drawer-close"' in resp.text


def test_drawer_active_tab_starts_as_imports(client: TestClient):
    resp = client.get("/")
    html = resp.text
    imp_idx = html.find(">Imports<")
    assert imp_idx > 0
    btn_start = html.rfind("<button", 0, imp_idx)
    btn_html = html[btn_start:imp_idx]
    assert 'data-tab="imports"' in btn_html


def test_drawer_imports_tab_lazy_loads_from_legacy_endpoint(client: TestClient):
    """The drawer's Imports tab pulls content from /imports/_legacy_page
    via HTMX so the home page doesn't pay the imports DB cost on every load."""
    resp = client.get("/")
    assert 'hx-get="/imports/_legacy_page"' in resp.text


def test_drawer_density_tab_renders_inside_drawer(tmp_path):
    """The Density tab inside the drawer renders the existing density
    toggle (Compact / Comfortable / Tax-view). We scope the assertion
    to the drawer container so we don't false-positive on per-page
    toggles still present in the page chrome (those are removed in E1).

    Note: _density_toggle.html renders label text with surrounding whitespace
    via Jinja `{{ dict[d] }}`, so we assert the label text and the preceding
    data-density attribute rather than `>Label<` with no whitespace.

    The density toggle is gated on show_switcher (requires at least one
    account), so we seed an account before fetching the page.
    """
    from net_alpha.config import Settings
    from net_alpha.db.connection import get_engine, init_db
    from net_alpha.db.repository import Repository
    from net_alpha.web.app import create_app

    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)
    repo.get_or_create_account("Schwab", "Tax")

    app = create_app(settings)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/")
    html = resp.text
    drawer_idx = html.find('id="settings-drawer-root"')
    assert drawer_idx > 0, "drawer root not found in HTML"
    # Use a generous window — density tab content sits ~4KB into the drawer
    drawer_html = html[drawer_idx : drawer_idx + 12000]
    # Check data-density attributes (unambiguous, no whitespace variation)
    assert 'data-density="compact"' in drawer_html
    assert 'data-density="comfortable"' in drawer_html
    assert 'data-density="tax"' in drawer_html
    # Check visible label text (may have surrounding whitespace from Jinja template)
    assert "Compact" in drawer_html
    assert "Comfortable" in drawer_html
    assert "Tax-view" in drawer_html
