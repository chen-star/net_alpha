"""Compute per-symbol open positions from trades + lots, scoped by account.

Pure function. Options are merged into their underlying ticker for
quantity/market value (equity-only) but contribute their cash flows to
cash_sunk_per_share. Period filtering applies to *realized P&L*, not to
the lots used for open positions (open positions are always "now").
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal

from net_alpha.models.domain import Lot, Trade
from net_alpha.portfolio.models import PositionRow
from net_alpha.pricing.provider import Quote


def compute_open_positions(
    *,
    trades: Iterable[Trade],
    lots: Iterable[Lot],
    prices: dict[str, Quote],
    period: tuple[int, int] | None = None,  # (year_start, year_end_exclusive); None = all time
    account: str | None = None,
) -> list[PositionRow]:
    """Return positions sorted by market value desc (None last)."""
    trades = list(trades)
    lots = list(lots)

    # Account scope
    if account:
        trades = [t for t in trades if t.account == account]
        lots = [lot for lot in lots if lot.account == account]

    # Equity-only quantities and basis come from open lots that are NOT options.
    qty_by_sym: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    open_cost_by_sym: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    accounts_by_sym: dict[str, set[str]] = defaultdict(set)
    for lot in lots:
        if lot.option_details is not None:
            continue  # options excluded from equity qty/basis (rolled into cash flows below)
        qty_by_sym[lot.ticker] += Decimal(str(lot.quantity))
        open_cost_by_sym[lot.ticker] += Decimal(str(lot.adjusted_basis))
        accounts_by_sym[lot.ticker].add(lot.account)

    # Cash flows include ALL trades on the underlying ticker (equity AND options).
    buys_by_sym: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    sells_by_sym: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    realized_by_sym: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for t in trades:
        sym = t.ticker
        accounts_by_sym[sym].add(t.account)  # ensure account is captured even if no open lot
        if t.action.lower() == "buy":
            buys_by_sym[sym] += Decimal(str(t.cost_basis or 0))
        elif t.action.lower() == "sell":
            sells_by_sym[sym] += Decimal(str(t.proceeds or 0))
            in_period = period is None or (t.date.year >= period[0] and t.date.year < period[1])
            if in_period:
                realized_by_sym[sym] += Decimal(str((t.proceeds or 0) - (t.cost_basis or 0)))

    rows: list[PositionRow] = []
    for sym, qty in qty_by_sym.items():
        if qty == 0:
            continue
        open_cost = open_cost_by_sym[sym]
        avg_basis = (open_cost / qty) if qty else Decimal("0")
        cash_sunk = (buys_by_sym[sym] - sells_by_sym[sym]) / qty if qty else Decimal("0")
        quote = prices.get(sym)
        market_value = (qty * quote.price) if quote else None
        unrealized = (market_value - open_cost) if market_value is not None else None
        rows.append(
            PositionRow(
                symbol=sym,
                accounts=tuple(sorted(accounts_by_sym[sym])),
                qty=qty,
                market_value=market_value,
                open_cost=open_cost,
                avg_basis=avg_basis,
                cash_sunk_per_share=cash_sunk,
                realized_pl=realized_by_sym[sym],
                unrealized_pl=unrealized,
            )
        )
    rows.sort(key=lambda r: (r.market_value is None, -(r.market_value or Decimal("0"))))
    return rows
