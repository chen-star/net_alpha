from pathlib import Path

TPL = Path(__file__).resolve().parents[2] / "src" / "net_alpha" / "web" / "templates"


def test_ticker_realized_card_is_feature():
    """The Realized P&L KPI is promoted to the page's single tier-1 surface."""
    src = (TPL / "ticker.html").read_text()
    assert "kpi panel-feature" in src


def test_ticker_has_five_countups():
    """Realized YTD + Lifetime, Disallowed YTD + Lifetime, and Open-lots count."""
    src = (TPL / "ticker.html").read_text()
    assert src.count('class="js-countup-num"') >= 5


def test_ticker_kpi_grid_reveal():
    """KPI tiles stagger in; realized tile is reveal child index 1."""
    src = (TPL / "ticker.html").read_text()
    assert "gap-4 mb-6 js-reveal" in src
    assert "--reveal-i: 1" in src


def test_ticker_tab_content_reveal():
    """Two reveal containers: the KPI grid and the tab-content/violations block."""
    src = (TPL / "ticker.html").read_text()
    assert src.count("js-reveal") >= 2
