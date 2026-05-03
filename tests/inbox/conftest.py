"""Shared helpers for inbox signal tests.

Each signal function is pure — it takes a duck-typed repo (MagicMock is
fine), an optional PricingService stub, and ``today``. These helpers
build the minimal fixtures.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from net_alpha.models.domain import (
    Lot,
    OptionDetails,
    Trade,
    WashSaleViolation,
)


def make_violation(
    *,
    vid: str = "1",
    ticker: str = "AAPL",
    loss_sale_date: date,
    disallowed_loss: float = 100.0,
    loss_account: str = "Schwab/Tax",
    buy_account: str = "Schwab/Tax",
) -> WashSaleViolation:
    return WashSaleViolation(
        id=vid,
        loss_trade_id="loss-trade",
        replacement_trade_id="rep-trade",
        confidence="Confirmed",
        disallowed_loss=disallowed_loss,
        matched_quantity=1.0,
        ticker=ticker,
        loss_account=loss_account,
        buy_account=buy_account,
        loss_sale_date=loss_sale_date,
        triggering_buy_date=loss_sale_date,
    )


def make_lot(
    *,
    lid: str = "1",
    trade_id: str = "t1",
    ticker: str = "AAPL",
    account: str = "Schwab/Tax",
    acquired: date = date(2024, 1, 1),
    quantity: float = 100.0,
    cost_basis: float = 1000.0,
    adjusted_basis: float | None = None,
    option: OptionDetails | None = None,
) -> Lot:
    return Lot(
        id=lid,
        trade_id=trade_id,
        account=account,
        date=acquired,
        ticker=ticker,
        quantity=quantity,
        cost_basis=cost_basis,
        adjusted_basis=adjusted_basis if adjusted_basis is not None else cost_basis,
        option_details=option,
    )


def make_repo(
    *,
    violations: list[WashSaleViolation] | None = None,
    lots: list[Lot] | None = None,
    trades: list[Trade] | None = None,
) -> MagicMock:
    repo = MagicMock()
    repo.all_violations.return_value = violations or []
    repo.all_lots.return_value = lots or []
    repo.all_trades.return_value = trades or []
    return repo


def make_prices_stub(prices: dict[str, Decimal]) -> MagicMock:
    """Stub of PricingService.get_prices: returns {symbol: Quote-like}."""
    svc = MagicMock()

    def _get(symbols: list[str]) -> dict[str, MagicMock]:
        out: dict[str, MagicMock] = {}
        for sym in symbols:
            if sym in prices:
                q = MagicMock()
                q.price = prices[sym]
                out[sym] = q
        return out

    svc.get_prices.side_effect = _get
    return svc
