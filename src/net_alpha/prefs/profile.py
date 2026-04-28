"""ProfileSettings — encapsulates the Section 3b visibility rule table.

Templates ask `profile.shows("surface")` instead of branching on profile
strings, so the rules live in one place and unknown surface keys default
to True (visible) with a warning logged.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from net_alpha.models.preferences import Density, Profile

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
        "conservative": ["open_position", "lifetime_growth", "cash"],
        "active": ["ytd_realized", "ytd_unrealized", "wash_impact", "open_position"],
        "options": ["ytd_realized", "wash_impact", "open_position", "cash"],
    },
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


DEFAULT_PROFILE_SETTINGS = ProfileSettings(profile="active", density="comfortable")
