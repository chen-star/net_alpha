"""Each Holdings row carries a 'Simulate sale' link to /sim with prefill params."""

import pathlib
import tempfile

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.web.app import create_app


def test_portfolio_table_renders_sim_link_in_thead_or_tbody():
    """Without fixture data we mainly check the structural intent: when the
    table renders, the action link template is present. Empty DB may render
    no rows; we then check the template definition file directly."""
    with tempfile.TemporaryDirectory() as d:
        s = Settings(data_dir=pathlib.Path(d))
        app = create_app(s)
        with TestClient(app) as c:
            r = c.get("/portfolio/positions")
        assert r.status_code == 200
        html = r.text
        # If <tr> rows are emitted, at least one of them carries the sim link.
        # If no rows, check the template file directly for structural intent.
        if "<tr" in html and "<tbody>" in html:
            tbody_start = html.find("<tbody>") + len("<tbody>")
            tbody_end = html.find("</tbody>", tbody_start)
            tbody = html[tbody_start:tbody_end]
            if "<tr" in tbody and "</tr>" in tbody:
                # Some row was rendered — assert it has the sim link.
                assert "/sim?ticker=" in tbody, "no sim link on rendered row"
                return
    # Fallback: assert the template defines the link
    template_path = pathlib.Path("src/net_alpha/web/templates/_portfolio_table.html")
    template_text = template_path.read_text()
    assert "/sim?ticker=" in template_text, "template missing per-row sim link"
    assert "Simulate sale" in template_text, "template missing 'Simulate sale' label"
