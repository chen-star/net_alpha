from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from pydantic import BaseModel


class BrokerLot(BaseModel):
    """One broker-supplied lot row, normalized across brokers."""

    symbol: str
    account_id: int
    acquired: date
    closed: date | None
    qty: float
    cost_basis: float
    proceeds: float | None
    wash_disallowed: float | None
    source_label: str  # e.g. "Schwab Realized G/L", "Schwab Unrealized"


class BrokerGLProvider(ABC):
    """Source of broker-truth lot detail for reconciliation."""

    @abstractmethod
    def supports(self, account_id: int) -> bool:
        """Whether this provider has data for the given account."""

    @abstractmethod
    def get_lot_detail(self, account_id: int, symbol: str) -> list[BrokerLot]:
        """Return all broker lots (open + closed) for the account/symbol."""
