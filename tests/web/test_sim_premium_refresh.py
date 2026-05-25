from pathlib import Path

TPL = Path(__file__).resolve().parents[2] / "src" / "net_alpha" / "web" / "templates"


def test_sim_form_is_feature():
    src = (TPL / "sim.html").read_text()
    assert "panel panel-feature mb-6" in src


def test_sim_sell_result_reveal_and_countup():
    src = (TPL / "_sim_sell_result.html").read_text()
    assert "grid grid-cols-2 gap-4 js-reveal" in src
    assert 'style="--reveal-i: {{ loop.index0 }}"' in src
    assert 'class="js-countup-num"' in src


def test_sim_buy_result_reveal_and_countup():
    src = (TPL / "_sim_buy_result.html").read_text()
    assert "grid grid-cols-2 gap-4 js-reveal" in src
    assert 'style="--reveal-i: {{ loop.index0 }}"' in src
    assert 'class="js-countup-num"' in src
