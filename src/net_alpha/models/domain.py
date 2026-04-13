from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class OptionDetails(BaseModel):
    """Option contract details parsed from symbol string."""

    strike: float
    expiry: date
    call_put: str  # "C" or "P"


class Trade(BaseModel):
    """A single trade (buy or sell) from a broker CSV."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    account: str
    date: date
    ticker: str
    action: str  # "Buy" or "Sell"
    quantity: float
    proceeds: Optional[float] = None
    cost_basis: Optional[float] = None
    basis_unknown: bool = False
    option_details: Optional[OptionDetails] = None
    raw_row_hash: Optional[str] = None
    schema_cache_id: Optional[str] = None

    def is_buy(self) -> bool:
        return self.action.lower() == "buy"

    def is_sell(self) -> bool:
        return self.action.lower() == "sell"

    def is_option(self) -> bool:
        return self.option_details is not None

    def is_loss(self) -> bool:
        if not self.is_sell() or self.basis_unknown:
            return False
        if self.proceeds is not None and self.cost_basis is not None:
            return self.proceeds < self.cost_basis
        return False

    def loss_amount(self) -> float:
        if self.is_loss() and self.proceeds is not None and self.cost_basis is not None:
            return self.cost_basis - self.proceeds
        return 0.0
