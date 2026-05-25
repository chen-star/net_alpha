from pathlib import Path

TPL = Path(__file__).resolve().parents[2] / "src" / "net_alpha" / "web" / "templates"


def test_performance_panel_hero_is_feature():
    src = (TPL / "_tax_performance_panel.html").read_text()
    assert "kpi kpi-hero panel-feature" in src


def test_performance_panel_has_four_countups():
    src = (TPL / "_tax_performance_panel.html").read_text()
    # 4 KPI values (pre-tax, tax bill, after-tax, tax drag) wrapped for count-up.
    assert src.count('class="js-countup-num"') >= 4


def test_performance_panel_reveal_container():
    src = (TPL / "_tax_performance_panel.html").read_text()
    assert "space-y-4 js-reveal" in src
    assert "--reveal-i:" in src
