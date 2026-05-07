from __future__ import annotations

from pathlib import Path

import jinja2
from fastapi.testclient import TestClient


def _env() -> jinja2.Environment:
    templates = Path(__file__).resolve().parents[2] / "src" / "net_alpha" / "web" / "templates"
    return jinja2.Environment(loader=jinja2.FileSystemLoader(str(templates)), autoescape=True)


def test_empty_state_renders_title_body_and_two_ctas() -> None:
    env = _env()
    tpl = env.get_template("_empty_state_hero.html")
    out = tpl.render(
        es_icon="wallet",
        es_title="No portfolio yet",
        es_body="Import a CSV or take a tour.",
        es_primary_label="Take the tour",
        es_primary_href="/welcome",
        es_secondary_label="Import CSV",
        es_secondary_href="/imports",
    )
    assert "No portfolio yet" in out
    assert "Import a CSV or take a tour." in out
    assert 'href="/welcome"' in out
    assert "Take the tour" in out
    assert 'href="/imports"' in out
    assert "Import CSV" in out


def test_empty_state_omits_primary_cta_when_label_blank() -> None:
    env = _env()
    tpl = env.get_template("_empty_state_hero.html")
    out = tpl.render(
        es_icon="upload",
        es_title="No imports yet",
        es_body="Drop a CSV.",
        es_primary_label="",
        es_primary_href="",
        es_secondary_label="",
        es_secondary_href="",
    )
    assert "No imports yet" in out
    assert "Drop a CSV." in out
    # Both CTAs suppressed
    assert 'href=""' not in out


def test_positions_empty_state_renders_take_the_tour(client: TestClient) -> None:
    resp = client.get("/positions")
    if resp.status_code in (302, 303, 307):
        resp = client.get(resp.headers["location"])
    body = resp.text
    assert "No positions to show" in body
    assert 'href="/welcome"' in body
    assert "Take the tour" in body


def test_tax_empty_state_renders(client: TestClient) -> None:
    resp = client.get("/tax")
    if resp.status_code in (302, 303, 307):
        resp = client.get(resp.headers["location"])
    assert "No tax data yet" in resp.text


def test_imports_empty_state_uses_shared_partial(client: TestClient) -> None:
    resp = client.get("/settings/imports")
    if resp.status_code in (301, 302, 303, 307):
        resp = client.get(resp.headers["location"])
    legacy = client.get("/imports/_legacy_page")
    assert "No imports yet" in legacy.text
    assert "Drop a Schwab" in legacy.text
