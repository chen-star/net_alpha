from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "src" / "net_alpha" / "web"
TPL = ROOT / "templates"
CSS = ROOT / "static" / "app.src.css"


def test_positions_pane_uses_feature_shadow():
    src = CSS.read_text()
    # The .positions-pane rule should elevate via --shadow-feature.
    idx = src.index(".positions-pane {")
    block = src[idx : idx + 200]
    assert "var(--shadow-feature)" in block


def test_positions_has_panel_level_reveal():
    src = (TPL / "positions.html").read_text()
    assert 'class="js-reveal"' in src
    assert "--reveal-i: 0" in src
    assert "--reveal-i: 1" in src
    assert "--reveal-i: 2" in src


def test_positions_reveal_not_on_rows():
    # Guard the density-first decision: no per-row reveal index.
    src = (TPL / "positions.html").read_text()
    assert "--reveal-i: {{ loop.index0 }}" not in src
