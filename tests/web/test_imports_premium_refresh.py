from pathlib import Path

TPL = Path(__file__).resolve().parents[2] / "src" / "net_alpha" / "web" / "templates"


def test_imports_table_is_feature():
    """The imports table is the tab's tier-1 surface."""
    src = (TPL / "_imports_table.html").read_text()
    assert "panel panel-feature" in src


def test_data_hygiene_headline_countups():
    """The two 'N items need attention' headline counts animate."""
    src = (TPL / "_data_hygiene.html").read_text()
    assert src.count("js-countup-num") >= 2
