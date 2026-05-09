"""Job A — refresh prices for everything held or targeted."""

from __future__ import annotations

from typing import Any


def run_price_refresh(*, repo: Any, pricing: Any) -> dict:
    """Pull fresh quotes for the union of held + targeted tickers."""
    held = set(repo.distinct_held_tickers())
    targeted = set(repo.distinct_target_tickers())
    symbols = sorted(held | targeted)
    if symbols:
        pricing.refresh(symbols)
    return {"symbols": len(symbols)}
