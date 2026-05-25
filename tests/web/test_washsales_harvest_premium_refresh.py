from pathlib import Path

TPL = Path(__file__).resolve().parents[2] / "src" / "net_alpha" / "web" / "templates"


def test_harvest_summary_is_feature():
    """The harvest summary tile is the planner's single tier-1 surface."""
    src = (TPL / "_harvest_summary.html").read_text()
    assert "panel-feature" in src


def test_harvest_summary_has_three_countups():
    """Selected count, loss harvested, and tax saved animate."""
    src = (TPL / "_harvest_summary.html").read_text()
    assert src.count("js-countup-num") >= 3


def test_harvest_fragment_has_no_reveal():
    """Deliberately reveal-free: the tile is HTMX-swapped on every toggle."""
    assert "js-reveal" not in (TPL / "_harvest_summary.html").read_text()
    assert "js-reveal" not in (TPL / "_harvest_plan.html").read_text()


def test_washsales_summary_is_feature():
    """The violations-summary strip is the wash-sales tab's feature surface."""
    src = (TPL / "_tax_wash_sales_tab.html").read_text()
    assert "panel panel-feature" in src


def test_washsales_has_two_countups():
    """Violation count and disallowed total animate."""
    src = (TPL / "_tax_wash_sales_tab.html").read_text()
    assert src.count("js-countup-num") >= 2


def test_washsales_content_reveal():
    """Watch + violations blocks stagger in on load."""
    src = (TPL / "_tax_wash_sales_tab.html").read_text()
    assert "js-reveal" in src
    assert "--reveal-i:" in src
