"""Every KPI tile carries a title= tooltip after the polish PR."""

import pathlib
import tempfile

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.web.app import create_app


def test_all_four_target_kpis_have_title():
    with tempfile.TemporaryDirectory() as d:
        s = Settings(data_dir=pathlib.Path(d))
        app = create_app(s)
        with TestClient(app) as c:
            r = c.get("/portfolio/kpis")
    html = r.text
    for slot in ("hero", "total_return", "realized", "unrealized", "cash"):
        anchor = f'data-kpi-slot="{slot}"'
        assert anchor in html, f"missing slot {slot}"
        # Locate the opening tag that contains data-kpi-slot=.
        # The tag starts with <div somewhere before the anchor, and ends
        # with the first > after the anchor.  title= must appear in that span.
        i = html.index(anchor)
        tag_start = html.rfind("<div", 0, i)
        tag_end = html.index(">", i)
        opening_tag = html[tag_start : tag_end + 1]
        assert "title=" in opening_tag, f"slot {slot!r} missing title= tooltip; opening tag: {opening_tag!r}"
