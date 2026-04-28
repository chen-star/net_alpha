# tests/prefs/test_effective_profile.py
import datetime

from net_alpha.models.preferences import AccountPreference
from net_alpha.prefs.profile import (
    DEFAULT_PROFILE_SETTINGS,
    resolve_effective_profile,
)


def _pref(aid, profile, density="comfortable"):
    return AccountPreference(
        account_id=aid,
        profile=profile,
        density=density,
        updated_at=datetime.datetime(2026, 4, 27, tzinfo=datetime.UTC),
    )


def test_no_preferences_returns_default():
    out = resolve_effective_profile(prefs=[], filter_account_id=None)
    assert out == DEFAULT_PROFILE_SETTINGS


def test_single_account_filter_uses_that_account():
    prefs = [_pref(1, "options"), _pref(2, "conservative")]
    out = resolve_effective_profile(prefs=prefs, filter_account_id=2)
    assert out.profile == "conservative"


def test_single_account_filter_missing_pref_falls_back():
    prefs = [_pref(1, "options")]
    out = resolve_effective_profile(prefs=prefs, filter_account_id=99)
    assert out.profile == "active"


def test_all_accounts_consistent_uses_shared_profile():
    prefs = [_pref(1, "options"), _pref(2, "options")]
    out = resolve_effective_profile(prefs=prefs, filter_account_id=None)
    assert out.profile == "options"


def test_all_accounts_mixed_falls_back_to_active():
    prefs = [_pref(1, "options"), _pref(2, "conservative")]
    out = resolve_effective_profile(prefs=prefs, filter_account_id=None)
    assert out.profile == "active"


def test_density_mirrors_profile_resolution():
    prefs = [_pref(1, "active", density="tax"), _pref(2, "active", density="tax")]
    out = resolve_effective_profile(prefs=prefs, filter_account_id=None)
    assert out.density == "tax"


def test_density_mixed_falls_back_to_comfortable():
    prefs = [_pref(1, "active", density="tax"), _pref(2, "active", density="compact")]
    out = resolve_effective_profile(prefs=prefs, filter_account_id=None)
    assert out.density == "comfortable"
