"""View models for the Action Inbox panel.

InboxItem is a derived view model — never persisted. The only persisted
state is the (signal-type-prefixed) dismiss_key in dismissed_inbox_items.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SignalType(StrEnum):
    WASH_REBUY = "wash_rebuy"
    LT_ELIGIBLE = "lt_eligible"
    OPTION_EXPIRY = "option_expiry"
    ASSIGNMENT_RISK = "assignment_risk"


class Severity(StrEnum):
    INFO = "info"
    WATCH = "watch"
    URGENT = "urgent"


class InboxItem(BaseModel):
    signal_type: SignalType
    dismiss_key: str
    ticker: str
    title: str
    subtitle: str
    event_date: date
    days_until: int  # negative if event already passed
    dollar_impact: Decimal | None
    severity: Severity
    deep_link: str
    extras: dict[str, Any] = Field(default_factory=dict)
