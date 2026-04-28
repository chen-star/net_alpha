# tests/web/test_density_toggle_in_pages.py
#
# After Phase 1 E1 the inline density toggle is removed from page chrome.
# The toggle now lives in the Settings drawer's Density tab (visible on every
# page via base.html). These tests verify the drawer on each page still carries
# the toggle — the per-page chrome assertions are replaced by the drawer-scoped
# check.  Per-page *absence* is covered by test_phase1_density_relocation.py.
from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.web.app import create_app


def _bootstrap(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)
    repo.get_or_create_account("Schwab", "Tax")
    return TestClient(create_app(settings))


def _drawer_html(html: str) -> str:
    """Return the portion of the page inside the settings drawer root."""
    idx = html.find('id="settings-drawer-root"')
    assert idx > 0, "settings-drawer-root not found in HTML"
    return html[idx : idx + 12000]


def test_holdings_renders_density_toggle(tmp_path):
    """Density toggle is present in the drawer on the /holdings page."""
    client = _bootstrap(tmp_path)
    html = client.get("/holdings").text
    drawer = _drawer_html(html)
    assert 'class="density-toggle' in drawer
    assert 'data-density="compact"' in drawer


def test_tax_renders_density_toggle(tmp_path):
    """Density toggle is present in the drawer on the /tax page."""
    client = _bootstrap(tmp_path)
    html = client.get("/tax").text
    drawer = _drawer_html(html)
    assert 'class="density-toggle' in drawer
    assert 'data-density="compact"' in drawer


def test_imports_renders_density_toggle(tmp_path):
    """Density toggle is present in the drawer on the /imports/_legacy_page."""
    client = _bootstrap(tmp_path)
    html = client.get("/imports/_legacy_page").text
    drawer = _drawer_html(html)
    assert 'class="density-toggle' in drawer
    assert 'data-density="compact"' in drawer
