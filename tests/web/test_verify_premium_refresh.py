from pathlib import Path

TPL = Path(__file__).resolve().parents[2] / "src" / "net_alpha" / "web" / "templates"


def test_verify_latest_run_is_feature():
    """The latest-run block is the page's single tier-1 surface."""
    src = (TPL / "verify" / "index.html").read_text()
    assert "panel panel-feature" in src


def test_verify_has_three_countups():
    """Failed / warned / total finding counts animate."""
    src = (TPL / "verify" / "index.html").read_text()
    assert src.count("js-countup-num") >= 3


def test_verify_reveal():
    """Latest-run + history blocks stagger in on load."""
    src = (TPL / "verify" / "index.html").read_text()
    assert "js-reveal" in src
    assert "--reveal-i:" in src
