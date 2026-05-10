"""Verify the palette JSON bootstrap is present on every primary page,
and that its contents parse as a dict with `pages` and `tickers` keys.
"""

from __future__ import annotations

import json
import re

import pytest

PAGES_TO_CHECK = [
    "/",
    "/positions",
    "/sim",
    "/tax",
    "/imports",
    "/settings",
]

SCRIPT_RE = re.compile(
    r'<script id="palette-index" type="application/json">(.*?)</script>',
    re.DOTALL,
)


@pytest.mark.parametrize("path", PAGES_TO_CHECK)
def test_palette_index_script_renders(client, path):
    resp = client.get(path)
    assert resp.status_code == 200, f"{path} returned {resp.status_code}"
    m = SCRIPT_RE.search(resp.text)
    assert m, f"{path}: <script id='palette-index'> missing"
    blob = json.loads(m.group(1))
    assert "pages" in blob
    assert "tickers" in blob
    assert isinstance(blob["pages"], list)
    assert isinstance(blob["tickers"], list)
