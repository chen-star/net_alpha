"""ProfileSettings — encapsulates the Section 3b visibility rule table.

Templates ask `profile.shows("surface")` instead of branching on profile
strings, so the rules live in one place and unknown surface keys default
to True (visible) with a warning logged.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from net_alpha.models.preferences import AccountPreference, Density, Profile

log = logging.getLogger(__name__)

# Visibility table — Section 3b of the spec. True = shown by default for that
# profile; False = hidden by default. Switching profile re-applies this map.
_VISIBILITY: dict[str, dict[Profile, bool]] = {
    "wash_watch_expanded": {"conservative": False, "active": True, "options": True},
    "lockout_calendar": {"conservative": False, "active": True, "options": True},
    "ltcg_approaching": {"conservative": True, "active": True, "options": True},
    "offset_budget": {"conservative": True, "active": True, "options": True},
    "year_end_projection": {"conservative": True, "active": True, "options": True},
    "traffic_light": {"conservative": True, "active": True, "options": True},
}


# Ordering table — Section 3b. Each entry maps a UI group key to the
# default ordering of slots within it. Templates iterate over the returned
# list and render the named slot. Unknown groups return [].
_ORDERING: dict[str, dict[Profile, list[str]]] = {
    "portfolio_kpi_hero": {
        # Wash impact moved to the Tax page (Phase 2.x) — this hero stays focused on
        # portfolio metrics only. Users can still surface wash impact via the slot
        # picker if they want it back.
        "conservative": ["open_position", "lifetime_growth", "cash"],
        "active": ["ytd_realized", "ytd_unrealized", "open_position", "cash"],
        "options": ["ytd_realized", "open_position", "cash"],
    },
}


# Columns table — Section 3b. Each profile's "extra" columns layered on top
# of the always-present base columns (symbol, qty, market value, P/L). The
# density "tax" overrides profile defaults and adds tax-specific columns.
_HOLDINGS_PROFILE_EXTRAS: dict[Profile, list[str]] = {
    "conservative": [],
    "active": ["days_held", "lt_st_split"],
    "options": ["days_held", "lt_st_split", "premium_received", "origin_event"],
}

_HOLDINGS_TAX_DENSITY_COLS: list[str] = [
    "lt_st_split",
    "days_to_ltcg",
    "harvestable",
    "premium_offset",
]

# Default tax tab per profile — Section 3b.
# "harvest" view was removed from /tax in Phase 1 IA (moved to /positions?view=at-loss).
# All profiles now default to "wash-sales".
_DEFAULT_TAX_TAB: dict[Profile, str] = {
    "conservative": "wash-sales",
    "active": "wash-sales",
    "options": "wash-sales",
}


class ProfileSettings(BaseModel):
    model_config = {"extra": "ignore"}

    profile: Profile = "active"
    density: Density = "comfortable"

    def shows(self, surface: str) -> bool:
        """Default visibility for a named surface.

        Unknown surface keys default to True (show) and emit a warning, so
        missing keys are caught in dev rather than silently hiding UI.
        """
        rule = _VISIBILITY.get(surface)
        if rule is None:
            log.warning("ProfileSettings.shows: unknown surface %r — defaulting True", surface)
            return True
        return rule[self.profile]

    def order(self, group: str) -> list[str]:
        """Default ordering for a named UI group."""
        rule = _ORDERING.get(group)
        if rule is None:
            return []
        return list(rule[self.profile])

    def default_columns(self, table: str) -> list[str]:
        """Default extra columns for a named table.

        - Density "compact": always [] (minimum columns).
        - Density "tax": overrides profile defaults; returns tax-specific cols.
        - Density "comfortable": profile-driven extras.
        """
        if table != "holdings":
            return []
        if self.density == "compact":
            return []
        if self.density == "tax":
            return list(_HOLDINGS_TAX_DENSITY_COLS)
        return list(_HOLDINGS_PROFILE_EXTRAS[self.profile])

    def default_tax_tab(self) -> str:
        """Default tab for /tax based on profile."""
        return _DEFAULT_TAX_TAB[self.profile]


DEFAULT_PROFILE_SETTINGS = ProfileSettings(profile="active", density="comfortable")


def resolve_effective_profile(
    *,
    prefs: list[AccountPreference],
    filter_account_id: int | None,
) -> ProfileSettings:
    """Compute the rendering profile for the current page request.

    - filter_account_id is set: use that account's pref, else default.
    - filter_account_id is None (All accounts):
        - all prefs share the same profile -> use it; else 'active'.
        - same rule applies to density independently.
    """
    if filter_account_id is not None:
        match = next((p for p in prefs if p.account_id == filter_account_id), None)
        if match is None:
            return DEFAULT_PROFILE_SETTINGS
        return ProfileSettings(profile=match.profile, density=match.density)

    if not prefs:
        return DEFAULT_PROFILE_SETTINGS

    profile_set = {p.profile for p in prefs}
    density_set = {p.density for p in prefs}
    profile = next(iter(profile_set)) if len(profile_set) == 1 else "active"
    density = next(iter(density_set)) if len(density_set) == 1 else "comfortable"
    return ProfileSettings(profile=profile, density=density)
