from pathlib import Path

TPL = Path(__file__).resolve().parents[2] / "src" / "net_alpha" / "web" / "templates"


def test_welcome_cards_feature_and_reveal():
    src = (TPL / "welcome.html").read_text()
    assert "panel panel-feature" in src
    assert "js-reveal" in src
    assert "--reveal-i:" in src


def test_backup_list_feature_and_reveal():
    src = (TPL / "backup.html").read_text()
    assert "panel panel-feature" in src
    assert "js-reveal" in src
    assert "--reveal-i:" in src
