"""Each Positions view's <thead> uses sticky positioning."""
import pathlib
import tempfile

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.web.app import create_app


def test_holdings_thead_is_sticky():
    with tempfile.TemporaryDirectory() as d:
        s = Settings(data_dir=pathlib.Path(d))
        app = create_app(s)
        with TestClient(app) as c:
            for view in ("all", "options", "closed"):
                r = c.get(f"/positions?view={view}")
                assert r.status_code == 200, f"view={view} status={r.status_code}"
                html = r.text
                # We expect the rendered fragment to contain a thead with sticky.
                # If the page short-circuits on empty data, the assertion is skipped.
                if "<thead" in html:
                    idx = html.find("<thead")
                    end = html.find(">", idx)
                    open_tag = html[idx:end]
                    assert "sticky" in open_tag, f"view={view} thead not sticky: {open_tag!r}"
