from __future__ import annotations

from pathlib import Path

import jinja2


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
