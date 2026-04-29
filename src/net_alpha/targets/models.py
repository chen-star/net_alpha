"""Domain types for position targets — what the user wants to hold."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class TargetUnit(StrEnum):
    USD = "usd"
    SHARES = "shares"


@dataclass(frozen=True)
class PositionTarget:
    symbol: str
    target_amount: Decimal
    target_unit: TargetUnit
    created_at: datetime
    updated_at: datetime
