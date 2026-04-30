"""Sim suggestion chips — pure-function picker for the /sim/suggestions endpoint.

Picks up to 3 chips: largest unrealized loss, wash-sale risk, largest gain.
Falls back to a single demo chip when the portfolio is empty.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal


@dataclass(frozen=True)
class Position:
    symbol: str
    account_label: str
    qty: Decimal
    cost_basis: Decimal  # total basis (qty * avg_basis)
    last_price: Decimal


@dataclass(frozen=True)
class LossClose:
    symbol: str
    account_label: str
    closed_on: date
    loss: Decimal  # negative
    lockout_clear: date  # date the wash window closes
    last_price: Decimal


SuggestionKind = Literal["largest_loss", "wash_risk", "largest_gain", "demo"]


@dataclass(frozen=True)
class SimSuggestion:
    kind: SuggestionKind
    label: str
    ticker: str
    qty: Decimal
    price: Decimal
    action: Literal["buy", "sell"]
    account: str | None


_DEMO_QTY = Decimal("10")


def _market_value(p: Position) -> Decimal:
    return p.qty * p.last_price


def _unrealized(p: Position) -> Decimal:
    return _market_value(p) - p.cost_basis


def top_suggestions(
    positions: list[Position],
    recent_loss_closes: list[LossClose],
    today: date,
) -> list[SimSuggestion]:
    """Return up to 3 chips. Empty portfolio (no positions and no losses) → 1 demo chip."""
    if not positions and not recent_loss_closes:
        return [
            SimSuggestion(
                kind="demo",
                label="Try a demo: TSLA 10 @ $180",
                ticker="TSLA",
                qty=_DEMO_QTY,
                price=Decimal("180"),
                action="sell",
                account=None,
            )
        ]

    chips: list[SimSuggestion] = []

    losers = [p for p in positions if _unrealized(p) < 0]
    if losers:
        worst = min(losers, key=lambda p: _unrealized(p))
        chips.append(
            SimSuggestion(
                kind="largest_loss",
                label=f"Largest loss: {worst.symbol} −${abs(_unrealized(worst)):.0f}",
                ticker=worst.symbol,
                qty=min(_DEMO_QTY, worst.qty),
                price=worst.last_price,
                action="sell",
                account=worst.account_label,
            )
        )

    active_wash = [w for w in recent_loss_closes if w.lockout_clear > today]
    if active_wash:
        wash = max(active_wash, key=lambda w: w.closed_on)
        chips.append(
            SimSuggestion(
                kind="wash_risk",
                label=f"Wash-sale risk: {wash.symbol}",
                ticker=wash.symbol,
                qty=_DEMO_QTY,
                price=wash.last_price,
                action="buy",
                account=wash.account_label,
            )
        )

    gainers = [p for p in positions if _unrealized(p) > 0]
    if gainers:
        best = max(gainers, key=lambda p: _unrealized(p))
        chips.append(
            SimSuggestion(
                kind="largest_gain",
                label=f"Largest gain: {best.symbol} +${_unrealized(best):.0f}",
                ticker=best.symbol,
                qty=min(_DEMO_QTY, best.qty),
                price=best.last_price,
                action="sell",
                account=best.account_label,
            )
        )

    return chips[:3]
