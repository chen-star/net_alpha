"""Account Pydantic model + AccountType enum.

Separate from the SQLModel AccountRow in db/tables.py — this is the
engine/API-layer model with strict validation. Keyed by the natural
(broker, label) tuple per the existing storage schema.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class AccountType(StrEnum):
    TAXABLE = "taxable"
    TRAD_IRA = "trad_ira"
    ROTH_IRA = "roth_ira"
    K401 = "401k"
    HSA = "hsa"
    OTHER = "other"

    @property
    def is_tax_advantaged(self) -> bool:
        return self in {
            AccountType.TRAD_IRA,
            AccountType.ROTH_IRA,
            AccountType.K401,
            AccountType.HSA,
        }


class Account(BaseModel):
    broker: str
    label: str
    type: AccountType = AccountType.TAXABLE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))  # noqa: UP017
