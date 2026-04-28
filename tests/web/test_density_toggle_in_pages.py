# tests/web/test_density_toggle_in_pages.py
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


def test_holdings_renders_density_toggle(tmp_path):
    client = _bootstrap(tmp_path)
    html = client.get("/holdings").text
    assert 'class="density-toggle' in html
    assert 'data-page-key="/positions"' in html


def test_tax_renders_density_toggle(tmp_path):
    client = _bootstrap(tmp_path)
    html = client.get("/tax").text
    assert 'class="density-toggle' in html
    assert 'data-page-key="/tax"' in html


def test_imports_renders_density_toggle(tmp_path):
    client = _bootstrap(tmp_path)
    html = client.get("/imports/_legacy_page").text
    assert 'class="density-toggle' in html
    assert 'data-page-key="/imports"' in html
