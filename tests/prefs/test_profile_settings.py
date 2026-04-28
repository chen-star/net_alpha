# tests/prefs/test_profile_settings.py
import pytest

from net_alpha.prefs.profile import DEFAULT_PROFILE_SETTINGS, ProfileSettings


def test_default_is_active_comfortable():
    assert DEFAULT_PROFILE_SETTINGS.profile == "active"
    assert DEFAULT_PROFILE_SETTINGS.density == "comfortable"


@pytest.mark.parametrize(
    "profile,surface,expected",
    [
        ("conservative", "lockout_calendar", False),
        ("active", "lockout_calendar", True),
        ("options", "lockout_calendar", True),
        ("conservative", "wash_watch_expanded", False),
        ("active", "wash_watch_expanded", True),
        ("options", "wash_watch_expanded", True),
        ("conservative", "ltcg_approaching", True),
        ("active", "ltcg_approaching", True),
        ("options", "ltcg_approaching", True),
        ("conservative", "offset_budget", True),
        ("conservative", "year_end_projection", True),
        ("conservative", "traffic_light", True),
    ],
)
def test_shows(profile, surface, expected):
    s = ProfileSettings(profile=profile, density="comfortable")
    assert s.shows(surface) == expected


def test_shows_unknown_surface_defaults_true():
    s = ProfileSettings(profile="active", density="comfortable")
    assert s.shows("nonexistent_surface") is True
