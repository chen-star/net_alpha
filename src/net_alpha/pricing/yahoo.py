"""Yahoo Finance price provider via yfinance.

Bulk fetches quotes per symbol (yfinance's batch API for `.info` is unreliable;
we iterate per symbol but keep the call inside one network session). Maps any
systemic exception to PriceFetchError; per-symbol misses (no price field) are
silently dropped from the result.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import yfinance as yf
from loguru import logger

from net_alpha.pricing.provider import PriceFetchError, PriceProvider, Quote


class YahooPriceProvider(PriceProvider):
    source_name = "yahoo"

    def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        if not symbols:
            return {}
        out: dict[str, Quote] = {}
        try:
            now = dt.datetime.now(dt.UTC)
            for symbol in symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    price = ticker.info.get("regularMarketPrice")
                except Exception as per_symbol_exc:
                    logger.warning("yahoo: fetch error for {}: {}", symbol, per_symbol_exc)
                    continue
                if price is None:
                    logger.warning("yahoo: no price for {}", symbol)
                    continue
                out[symbol] = Quote(
                    symbol=symbol,
                    price=Decimal(str(price)),
                    as_of=now,
                    source=self.source_name,
                )
        except Exception as exc:  # systemic failure outside the per-symbol loop
            raise PriceFetchError(str(exc), symbols=symbols) from exc
        return out
