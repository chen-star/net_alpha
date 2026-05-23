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
        r = c.get("/tax/harvest/plan", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert 'id="harvest-queue-region"' in r.text


def test_plan_endpoint_accepts_custom_budget():
    with _client() as c:
        r = c.get("/tax/harvest/plan?mode=custom&custom_budget=500", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert 'id="harvest-queue-region"' in r.text


def test_plan_endpoint_manual_mode_renders():
    with _client() as c:
        r = c.get("/tax/harvest/plan?mode=manual", headers={"HX-Request": "true"})
    assert r.status_code == 200


def test_plan_endpoint_exclude_locked_off_includes_setting():
    with _client() as c:
        r = c.get("/tax/harvest/plan?exclude_locked=0", headers={"HX-Request": "true"})
    assert r.status_code == 200


# --- audit #21: hidden-input idiom for exclude_locked checkbox -----------------
# Browsers omit unchecked checkboxes from form submission. A bare
# `<input type="checkbox" name="exclude_locked">` paired with a server-side
# `exclude_locked: bool = True` default means the user can never turn the
# filter off — every uncheck is silently re-enabled by the default. The fix
# is a hidden "0" sibling submitted BEFORE the checkbox; FastAPI's bool
# coercion of repeated query params keeps the last value.


def test_harvest_summary_has_hidden_zero_before_checkbox():
    """The fix: hidden '0' must precede the checkbox in form order."""
    with _client() as c:
        r = c.get(
            "/tax/harvest/plan",
            headers={"HX-Request": "true", "HX-Target": "harvest-summary"},
        )
    assert r.status_code == 200
    body = r.text
    hidden_idx = body.find('<input type="hidden" name="exclude_locked" value="0">')
    checkbox_idx = body.find('<input type="checkbox" name="exclude_locked"')
    assert hidden_idx != -1, "hidden exclude_locked=0 sentinel must be present"
    assert checkbox_idx != -1, "exclude_locked checkbox must be present"
    assert hidden_idx < checkbox_idx, "hidden 0 must come BEFORE the checkbox so the 1 wins"


def test_uncheck_actually_disables_filter():
    """Unchecked browser submission sends only `exclude_locked=0` → server sees False."""
    with _client() as c:
        r = c.get(
            "/tax/harvest/plan?exclude_locked=0",
            headers={"HX-Request": "true", "HX-Target": "harvest-summary"},
        )
    assert r.status_code == 200
    # When unchecked the rendered checkbox tag must NOT carry the `checked` attr.
    # Slice the substring starting at the checkbox open tag and ending at its close.
    cb_open = r.text.find('<input type="checkbox" name="exclude_locked"')
    assert cb_open != -1
    cb_tag = r.text[cb_open : r.text.find(">", cb_open) + 1]
    assert "checked" not in cb_tag, f"unchecked GET must not re-render `checked`: {cb_tag!r}"


def test_default_get_renders_checked_box():
    """No exclude_locked param → server default True → checkbox renders checked."""
    with _client() as c:
        r = c.get(
            "/tax/harvest/plan",
            headers={"HX-Request": "true", "HX-Target": "harvest-summary"},
        )
    assert r.status_code == 200
    cb_open = r.text.find('<input type="checkbox" name="exclude_locked"')
    cb_tag = r.text[cb_open : r.text.find(">", cb_open) + 1]
    assert "checked" in cb_tag, f"default state should render checked: {cb_tag!r}"


def test_check_actually_enables_filter():
    """Checked browser submission sends both `0` and `1`; FastAPI takes last → True."""
    with _client() as c:
        r = c.get(
            "/tax/harvest/plan?exclude_locked=0&exclude_locked=1",
            headers={"HX-Request": "true", "HX-Target": "harvest-summary"},
        )
    assert r.status_code == 200
    # Checked state must render the `checked` attribute on the checkbox tag.
    cb_open = r.text.find('<input type="checkbox" name="exclude_locked"')
    cb_tag = r.text[cb_open : r.text.find(">", cb_open) + 1]
    assert "checked" in cb_tag, f"checked GET should re-render `checked`: {cb_tag!r}"
    # Hidden sentinel + checkbox pair must still be present and ordered.
    hidden_idx = r.text.find('<input type="hidden" name="exclude_locked" value="0">')
    assert hidden_idx != -1 and hidden_idx < cb_open
