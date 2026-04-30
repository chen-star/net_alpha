"""The Imports data-quality section uses collapsible groups (Missing basis,
No price quote, Missing dates), most-actionable open by default."""

import pathlib
import tempfile

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.web.app import create_app


def test_imports_page_renders_or_falls_back_cleanly():
    """Smoke check: the imports page must render successfully on an empty DB."""
    with tempfile.TemporaryDirectory() as d:
        s = Settings(data_dir=pathlib.Path(d))
        app = create_app(s)
        with TestClient(app) as c:
            r = c.get("/imports/_legacy_page")
        assert r.status_code == 200


def test_imports_template_uses_dq_groups_structure():
    """Static template inspection: the bucket-rendering block exists."""
    template_paths = list(pathlib.Path("src/net_alpha/web/templates").glob("imports.html"))
    template_paths += list(pathlib.Path("src/net_alpha/web/templates").glob("_data_hygiene.html"))
    found = False
    for p in template_paths:
        text = p.read_text()
        if "dq_groups" in text and "Missing basis" in text:
            found = True
            break
    assert found, "Expected dq_groups + 'Missing basis' bucket in either imports.html or _data_hygiene.html"
