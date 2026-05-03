"""Action Inbox configuration loaded from ~/.net_alpha/config.yaml `inbox:` section.

All keys optional; defaults baked into InboxConfig field defaults.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class InboxConfig(BaseModel):
    wash_rebuy_visible_days: int = Field(default=14, ge=0)
    lt_lookahead_days: int = Field(default=60, ge=1)
    option_expiry_lookahead_days: int = Field(default=14, ge=0)
    assignment_risk_window_days: int = Field(default=7, ge=0)


def load_inbox_config(path: Path) -> InboxConfig:
    if not path.exists():
        return InboxConfig()
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        return InboxConfig()
    section = data.get("inbox") if isinstance(data, dict) else None
    if not isinstance(section, dict):
        return InboxConfig()
    return InboxConfig(**section)
