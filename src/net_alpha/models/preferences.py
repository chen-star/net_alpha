"""Domain model for per-account user preferences (v9 schema)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Profile = Literal["conservative", "active", "options"]
Density = Literal["compact", "comfortable", "tax"]


class AccountPreference(BaseModel):
    model_config = {"extra": "ignore"}

    account_id: int
    profile: Profile = "active"
    density: Density = "comfortable"
    updated_at: datetime
