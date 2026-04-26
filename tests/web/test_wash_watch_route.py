from __future__ import annotations

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.web.app import create_app


def _client(tmp_path):
    return TestClient(create_app(Settings(data_dir=tmp_path)))


def test_wash_watch_fragment_empty(tmp_path):
    client = _client(tmp_path)
    r = client.get("/portfolio/wash-watch")
    assert r.status_code == 200
    assert "All clear" in r.text or "no loss closes" in r.text


def test_wash_watch_fragment_with_account_filter(tmp_path):
    client = _client(tmp_path)
    r = client.get("/portfolio/wash-watch?account=Tax")
    assert r.status_code == 200
