# tests/web/test_density_js_present.py
from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.web.app import create_app


def test_density_js_loaded_in_base(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    app = create_app(settings)
    client = TestClient(app)
    html = client.get("/").text
    assert "/static/density.js" in html


def test_density_js_served(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    app = create_app(settings)
    client = TestClient(app)
    resp = client.get("/static/density.js")
    assert resp.status_code == 200
    assert "applyDensityFromLocalStorage" in resp.text
    assert "recordDensityOverride" in resp.text
