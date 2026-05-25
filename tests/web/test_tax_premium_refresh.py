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


def test_projection_card_feature_and_countup():
    src = (TPL / "_projection_card.html").read_text()
    assert 'class="kpi panel-feature"' in src
    assert 'class="js-countup-num"' in src
    assert 'style="--reveal-i: 0"' in src  # card is reveal child 0 of the tab section


def test_projection_tab_has_no_reveal_container():
    """The projection tab is returned as an HTMX swap on every 'Save config'
    (hx-target=#projection-tab-content). It must NOT carry an entrance reveal,
    or the staggered fade-up replays on each save."""
    src = (TPL / "_projection_tab.html").read_text()
    assert "js-reveal" not in src
