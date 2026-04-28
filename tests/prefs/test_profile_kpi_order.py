# tests/prefs/test_profile_kpi_order.py
from net_alpha.prefs.profile import ProfileSettings


def test_kpi_hero_order_conservative():
    s = ProfileSettings(profile="conservative", density="comfortable")
    assert s.order("portfolio_kpi_hero") == [
        "open_position",
        "lifetime_growth",
        "cash",
    ]


def test_kpi_hero_order_active():
    s = ProfileSettings(profile="active", density="comfortable")
    assert s.order("portfolio_kpi_hero") == [
        "ytd_realized",
        "ytd_unrealized",
        "wash_impact",
        "open_position",
    ]


def test_kpi_hero_order_options():
    s = ProfileSettings(profile="options", density="comfortable")
    assert s.order("portfolio_kpi_hero") == [
        "ytd_realized",
        "wash_impact",
        "open_position",
        "cash",
    ]


def test_order_unknown_group_returns_empty():
    s = ProfileSettings(profile="active", density="comfortable")
    assert s.order("nonexistent_group") == []
