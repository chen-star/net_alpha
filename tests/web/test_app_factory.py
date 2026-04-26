from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.web.app import create_app


def test_create_app_returns_fastapi_instance(tmp_path):
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings)
    assert app.title == "net-alpha"


def test_healthz_returns_ok(tmp_path):
    settings = Settings(data_dir=tmp_path)
    client = TestClient(create_app(settings))
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_root_renders_base_html_with_disclaimer(tmp_path):
    settings = Settings(data_dir=tmp_path)
    client = TestClient(create_app(settings))
    resp = client.get("/")
    assert resp.status_code == 200
    assert "<!DOCTYPE html>" in resp.text
    assert "Portfolio" in resp.text
    assert "Consult a tax professional" in resp.text


def test_etf_pairs_loaded_in_app_state(tmp_path):
    from net_alpha.config import Settings
    from net_alpha.web.app import create_app

    settings = Settings(data_dir=tmp_path)
    app = create_app(settings)
    # ETF pairs should be loaded once at app creation; bundled defaults present.
    assert "SP500" in app.state.etf_pairs or len(app.state.etf_pairs) > 0
