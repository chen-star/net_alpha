# tests/prefs/test_profile_columns.py
from net_alpha.prefs.profile import ProfileSettings


def test_holdings_columns_conservative():
    s = ProfileSettings(profile="conservative", density="comfortable")
    cols = s.default_columns("holdings")
    assert "days_held" not in cols
    assert "lt_st_split" not in cols
    assert "premium_received" not in cols
    assert "origin_event" not in cols


def test_holdings_columns_active():
    s = ProfileSettings(profile="active", density="comfortable")
    cols = s.default_columns("holdings")
    assert "days_held" in cols
    assert "lt_st_split" in cols
    assert "premium_received" not in cols


def test_holdings_columns_options():
    s = ProfileSettings(profile="options", density="comfortable")
    cols = s.default_columns("holdings")
    assert "days_held" in cols
    assert "lt_st_split" in cols
    assert "premium_received" in cols
    assert "origin_event" in cols


def test_holdings_columns_compact_strips_extras():
    s = ProfileSettings(profile="options", density="compact")
    cols = s.default_columns("holdings")
    # compact: minimum columns regardless of profile
    assert cols == []


def test_holdings_columns_tax_view_adds_tax_specific():
    s = ProfileSettings(profile="conservative", density="tax")
    cols = s.default_columns("holdings")
    # tax-view overrides profile defaults; adds tax-specific columns
    assert "lt_st_split" in cols
    assert "days_to_ltcg" in cols
    assert "harvestable" in cols


def test_default_tax_tab_per_profile():
    # Phase 1 IA critical fix #2: harvest moved to /positions?view=at-loss.
    # All profiles now default to wash-sales on /tax.
    assert ProfileSettings(profile="conservative", density="comfortable").default_tax_tab() == "wash-sales"
    assert ProfileSettings(profile="active", density="comfortable").default_tax_tab() == "wash-sales"
    assert ProfileSettings(profile="options", density="comfortable").default_tax_tab() == "wash-sales"
