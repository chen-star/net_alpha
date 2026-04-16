from net_alpha.cli.rebuys import _days_remaining_style


def test_days_remaining_style_urgent():
    assert "bold red" in _days_remaining_style(5)


def test_days_remaining_style_warning():
    assert "yellow" in _days_remaining_style(10)


def test_days_remaining_style_safe():
    assert _days_remaining_style(20) == ""
