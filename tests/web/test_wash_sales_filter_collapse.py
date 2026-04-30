"""Wash-sales filter collapsible behavior."""
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


def test_filter_collapsed_with_no_query():
    with _client() as c:
        r = c.get("/wash-sales")
    html = r.text
    idx = html.find("<details")
    assert idx != -1, "expected a <details> wrapping the filter"
    end = html.find(">", idx)
    open_tag = html[idx:end]
    assert "open" not in open_tag, f"filter should be collapsed by default; got {open_tag!r}"


def test_filter_open_when_ticker_param_set():
    with _client() as c:
        r = c.get("/wash-sales?ticker=TSLA")
    html = r.text
    idx = html.find("<details")
    assert idx != -1
    end = html.find(">", idx)
    open_tag = html[idx:end]
    assert "open" in open_tag, f"filter should be expanded when a filter is active; got {open_tag!r}"
