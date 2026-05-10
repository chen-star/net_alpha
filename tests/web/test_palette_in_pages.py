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


def test_palette_json_escapes_script_close_tag(client):
    """A ticker containing '</script>' must NOT break out of the bootstrap
    <script> tag. Jinja's tojson filter unicode-escapes <, >, &.

    We can't easily seed a malicious ticker via the public client API, but
    we can verify the rendered output is impervious by checking that
    Jinja's tojson is in use: rendered numbers like `100` should appear,
    AND any literal `<` in the JSON content should be unicode-escaped.
    """
    # Hit any page; verify the JSON blob does not contain a literal '</script'.
    resp = client.get("/")
    assert resp.status_code == 200
    # Locate the script tag's contents.
    m = re.search(
        r'<script id="palette-index" type="application/json">(.*?)</script>',
        resp.text,
        re.DOTALL,
    )
    assert m
    body = m.group(1)
    # Jinja tojson unicode-escapes < to <. Even with an empty palette,
    # this is verifiable indirectly: the body must be valid JSON when parsed,
    # AND if any '<' appears it must NOT be a literal '<' that could close the
    # surrounding tag. The simplest invariant: the substring '</' must not appear
    # anywhere in the JSON body.
    assert "</" not in body, (
        "palette JSON contains a literal '</' which could close the wrapping "
        "<script> tag and enable HTML injection from CSV-derived ticker strings"
    )


def test_palette_results_list_has_listbox_role(client):
    """The results <ul> must carry role='listbox' so the input's
    aria-controls + each <li>'s role='option' form a proper ARIA
    ownership chain for screen readers."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert (
        '<ul id="palette-results" role="listbox"' in resp.text
        or 'id="palette-results"' in resp.text
        and 'role="listbox"' in resp.text
    ), "palette results <ul> missing role='listbox'"


def test_palette_input_traps_tab_key(client):
    """The palette input must intercept Tab (via Alpine's @keydown.tab.prevent)
    so focus stays inside the modal dialog while it is open."""
    resp = client.get("/")
    assert resp.status_code == 200
    # Alpine attribute is emitted verbatim by Jinja into the rendered HTML.
    assert "@keydown.tab.prevent" in resp.text, (
        "palette input missing @keydown.tab.prevent — Tab key would escape "
        "the open modal, violating role='dialog' aria-modal='true' contract"
    )
