from __future__ import annotations

import hashlib
from datetime import date

from pydantic import BaseModel


class RealizedGLLot(BaseModel):
    """One tax-lot row from a Schwab Realized G/L CSV.

    Multiple lots can map to one Sell trade (one row per buy lot consumed).
    """

    account_display: str
    symbol_raw: str
    ticker: str
    closed_date: date
    opened_date: date
    quantity: float
    proceeds: float
    cost_basis: float
    unadjusted_cost_basis: float
    wash_sale: bool
    disallowed_loss: float
    term: str  # "Short Term" | "Long Term"

    option_strike: float | None = None
    option_expiry: str | None = None
    option_call_put: str | None = None

    def compute_natural_key(self) -> str:
        """SHA256 over invariant fields. Used for idempotent dedup on re-import."""
        parts = [
            self.account_display,
            self.symbol_raw,
            self.closed_date.isoformat(),
            self.opened_date.isoformat(),
            f"{self.quantity:.8f}",
            f"{self.cost_basis:.8f}",
            f"{self.proceeds:.8f}",
        ]
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
