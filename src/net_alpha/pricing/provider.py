"""Pricing provider abstraction — Quote model + PriceProvider ABC.

External price providers (Yahoo, Schwab, etc.) implement PriceProvider.
Quote is the normalized result type returned for a single symbol.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator


class Quote(BaseModel):
    model_config = {"frozen": True}
    symbol: str
    price: Decimal
    as_of: datetime
    source: str

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        return v


class PriceFetchError(Exception):
    """Raised when a provider fails to fetch quotes for the requested symbols."""

    def __init__(self, message: str, symbols: list[str] | None = None) -> None:
        super().__init__(message)
        self.symbols = symbols or []


class PriceProvider(ABC):
    """Fetch live quotes for a list of symbols."""

    @abstractmethod
    def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Return {symbol: Quote} for symbols the provider could fetch.

        Symbols missing from the result were unavailable. Raises PriceFetchError
        on systemic failures (network down, rate-limit), not on per-symbol misses.
        """
