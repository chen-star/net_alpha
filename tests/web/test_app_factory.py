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
