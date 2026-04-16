from datetime import date, timedelta

from net_alpha.cli.status import _days_ago_str, _staleness_style


def test_days_ago_str_recent():
    today = date.today()
    recent = (today - timedelta(days=3)).isoformat()
    assert "3 days ago" in _days_ago_str(recent)


def test_days_ago_str_today():
    today = date.today().isoformat()
    assert "today" in _days_ago_str(today)


def test_staleness_style_fresh():
    today = date.today()
    recent = (today - timedelta(days=5)).isoformat()
    assert _staleness_style(recent) == ""


def test_staleness_style_stale():
    today = date.today()
    stale = (today - timedelta(days=35)).isoformat()
    assert "yellow" in _staleness_style(stale)
