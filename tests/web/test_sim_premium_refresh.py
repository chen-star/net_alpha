from pathlib import Path

TPL = Path(__file__).resolve().parents[2] / "src" / "net_alpha" / "web" / "templates"


def test_sim_form_is_feature():
    src = (TPL / "sim.html").read_text()
    assert "panel panel-feature mb-6" in src


def test_sim_sell_result_countup_without_reveal():
    """HTMX swap fragment: count-up is fine, but the entrance reveal must NOT
    be present — it replays jarringly on every Run-sim swap."""
    src = (TPL / "_sim_sell_result.html").read_text()
    assert "js-reveal" not in src
    assert 'class="js-countup-num"' in src


def test_sim_buy_result_countup_without_reveal():
    src = (TPL / "_sim_buy_result.html").read_text()
    assert "js-reveal" not in src
    assert 'class="js-countup-num"' in src
