"""Yahoo Finance price provider via yfinance.

Bulk fetches quotes per symbol (yfinance's batch API for `.info` is unreliable;
we iterate per symbol but keep the call inside one network session). Maps any
systemic exception to PriceFetchError; per-symbol misses (no price field) are
silently dropped from the result.
"""

from __future__ import annotations

import datetime as dt
from datetime import date as _date
from decimal import Decimal

import yfinance as yf
from loguru import logger

from net_alpha.pricing.provider import PriceFetchError, PriceProvider, Quote, SplitEvent


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
                    info = ticker.info
                    price = info.get("regularMarketPrice")
                    prev = info.get("regularMarketPreviousClose")
                except Exception as per_symbol_exc:
                    logger.warning("yahoo: fetch error for {}: {}", symbol, per_symbol_exc)
                    continue
                if price is None:
                    # Common for delisted/illiquid tickers — UI already shows "—".
                    # Keep at debug to avoid noisy logs on every refresh cycle.
                    logger.debug("yahoo: no price for {}", symbol)
                    continue
                out[symbol] = Quote(
                    symbol=symbol,
                    price=Decimal(str(price)),
                    previous_close=Decimal(str(prev)) if prev is not None else None,
                    as_of=now,
                    source=self.source_name,
                )
        except Exception as exc:  # systemic failure outside the per-symbol loop
            raise PriceFetchError(str(exc), symbols=symbols) from exc
        return out

    def get_historical_close(self, symbol: str, on: _date) -> Decimal | None:
        """Fetch the close price for `symbol` on `on`. Returns None on any
        error (no row, network failure, parse error). yfinance fetches a
        single-day window via [start, end+1)."""
        import datetime as _dt
        end = on + _dt.timedelta(days=1)
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=on.isoformat(), end=end.isoformat(), auto_adjust=False)
            if hist is None or hist.empty:
                return None
            close = hist["Close"].iloc[0]
            return Decimal(str(round(float(close), 4)))
        except Exception as exc:
            logger.debug("yahoo: historical close fetch error for {} on {}: {}", symbol, on, exc)
            return None

    def fetch_splits(self, symbol: str) -> list[SplitEvent]:
        """Fetch all known splits for a symbol from yfinance. Returns [] on any error."""
        try:
            ticker = yf.Ticker(symbol)
            series = ticker.splits  # pandas Series indexed by datetime
        except Exception as exc:
            logger.warning("yahoo: split fetch error for {}: {}", symbol, exc)
            return []
        events: list[SplitEvent] = []
        try:
            for ts, ratio in series.items():
                d = ts.date() if hasattr(ts, "date") else _date.fromisoformat(str(ts)[:10])
                events.append(SplitEvent(symbol=symbol, split_date=d, ratio=float(ratio)))
        except Exception as exc:
            logger.warning("yahoo: split parse error for {}: {}", symbol, exc)
            return []
        events.sort(key=lambda e: e.split_date)
        return events
