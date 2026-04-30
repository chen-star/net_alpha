"""When the user lands on /tax?view=harvest with no params, the
'Currently harvestable only' checkbox is checked by default."""

import pathlib
import tempfile

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.web.app import create_app


def test_harvest_only_harvestable_checked_by_default():
    with tempfile.TemporaryDirectory() as d:
        s = Settings(data_dir=pathlib.Path(d))
        app = create_app(s)
        with TestClient(app) as c:
            r = c.get("/tax?view=harvest")
    assert r.status_code == 200
    html = r.text
    idx = html.find('name="only_harvestable"')
    assert idx != -1, "only_harvestable checkbox not found"
    # Inspect the input tag for `checked`.
    start = html.rfind("<input", 0, idx)
    end = html.find(">", idx)
    open_tag = html[start:end]
    assert "checked" in open_tag, f"only_harvestable should default checked; got {open_tag!r}"
