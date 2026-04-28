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
    # wash_impact moved to the Tax page — Portfolio hero stays portfolio-focused.
    assert s.order("portfolio_kpi_hero") == [
        "ytd_realized",
        "ytd_unrealized",
        "open_position",
        "cash",
    ]


def test_kpi_hero_order_options():
    s = ProfileSettings(profile="options", density="comfortable")
    assert s.order("portfolio_kpi_hero") == [
        "ytd_realized",
        "open_position",
        "cash",
    ]


def test_no_profile_orders_wash_impact():
    """wash_impact is no longer a default Portfolio hero slot in any profile —
    it's surfaced on the Tax page wash-sales tab."""
    for profile in ("conservative", "active", "options"):
        s = ProfileSettings(profile=profile, density="comfortable")
        assert "wash_impact" not in s.order("portfolio_kpi_hero")


def test_order_unknown_group_returns_empty():
    s = ProfileSettings(profile="active", density="comfortable")
    assert s.order("nonexistent_group") == []
