from __future__ import annotations

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.web.app import create_app


def _client(tmp_path):
    return TestClient(create_app(Settings(data_dir=tmp_path)))


def test_allocation_fragment_empty(tmp_path):
    client = _client(tmp_path)
    r = client.get("/portfolio/allocation")
    assert r.status_code == 200
    assert "No priced open positions" in r.text


def test_allocation_fragment_with_account_filter(tmp_path):
    client = _client(tmp_path)
    r = client.get("/portfolio/allocation?account=Tax")
    assert r.status_code == 200


def test_old_treemap_route_returns_404(tmp_path):
    client = _client(tmp_path)
    r = client.get("/portfolio/treemap")
    assert r.status_code == 404
