"""Tests for the GET /sim/suggestions chip-strip endpoint."""
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


def test_endpoint_returns_at_least_one_chip():
    """On a fresh empty DB, the demo-fallback chip should render with a valid /sim href."""
    with _client() as c:
        r = c.get("/sim/suggestions")
    assert r.status_code == 200
    assert "/sim?" in r.text


def test_chips_strip_loaded_lazily_on_sim_page():
    """The Sim form page emits a placeholder div that lazy-loads /sim/suggestions."""
    with _client() as c:
        r = c.get("/sim")
    assert r.status_code == 200
    html = r.text
    assert 'hx-get="/sim/suggestions"' in html or "hx-get='/sim/suggestions'" in html


def test_demo_chip_uses_safe_action():
    """Demo chip should propose a sell of TSLA 10 @ 180 with action=sell."""
    with _client() as c:
        r = c.get("/sim/suggestions")
    html = r.text
    assert "ticker=TSLA" in html
    assert "action=sell" in html
