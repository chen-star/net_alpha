"""Tests for the GET /tax/harvest/plan endpoint."""
import pathlib
import tempfile

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.web.app import create_app


def _client():
    d = tempfile.mkdtemp()
    s = Settings(data_dir=pathlib.Path(d))
    app = create_app(s)
    return TestClient(app)


def test_plan_endpoint_returns_fragment_with_region_id():
    with _client() as c:
        r = c.get("/tax/harvest/plan")
    assert r.status_code == 200
    assert 'id="harvest-queue-region"' in r.text


def test_plan_endpoint_accepts_custom_budget():
    with _client() as c:
        r = c.get("/tax/harvest/plan?mode=custom&custom_budget=500")
    assert r.status_code == 200
    assert 'id="harvest-queue-region"' in r.text


def test_plan_endpoint_manual_mode_renders():
    with _client() as c:
        r = c.get("/tax/harvest/plan?mode=manual")
    assert r.status_code == 200


def test_plan_endpoint_exclude_locked_off_includes_setting():
    with _client() as c:
        r = c.get("/tax/harvest/plan?exclude_locked=0")
    assert r.status_code == 200
