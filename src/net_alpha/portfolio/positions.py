"""Compute per-symbol open positions from trades + lots, scoped by account.

Pure function. Options are merged into their underlying ticker for
quantity/market value (equity-only) but contribute their cash flows to
cash_sunk_per_share. Period filtering applies to *realized P&L*, not to
the lots used for open positions (open positions are always "now").

Lots stored in the DB always carry the original buy quantity — the wash-sale
engine never decrements them when sells occur. This module FIFO-consumes the
oldest lot first against (a) sells in the trades table and (b) closed-quantity
totals from the Realized G/L import (used as a fallback when the user imported
G/L without the matching Transaction History, so the trade-table sells are
incomplete). The larger of the two sources wins per (account, ticker).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal

from net_alpha.models.domain import Lot, Trade
from net_alpha.portfolio.models import PositionRow
from net_alpha.pricing.provider import Quote


def consume_lots_fifo(
    *,
    lots: Iterable[Lot],
    trades: Iterable[Trade],
    gl_closures: dict[tuple[str, str], float] | None = None,
) -> list[tuple[Lot, Decimal, Decimal]]:
    """FIFO-consume equity lots by sells (trades) and GL closures.

    Returns a list of (original_lot, remaining_qty, remaining_adjusted_basis).
    Option lots pass through with full quantity/basis. Lots fully consumed
    have remaining_qty == 0 (still returned so callers can inspect).

    For each (account, ticker), closed_qty = max(sum_sells_in_trades, gl_closures).
    GL is treated as canonical when it exceeds the trade-side sells, since the
    Realized G/L CSV captures every closed lot regardless of whether the
    matching Sell trade was imported.
    """
    gl_closures = gl_closures or {}
    lots_list = list(lots)

    # Total equity sells per (account, ticker) from the trade table.
    sells_qty: dict[tuple[str, str], float] = defaultdict(float)
    for t in trades:
        if t.option_details is not None:
            continue
        if t.action.lower() == "sell":
            sells_qty[(t.account, t.ticker)] += float(t.quantity)

    # Combine with GL closures, taking the larger value per key.
    keys = set(sells_qty.keys()) | set(gl_closures.keys())
    closed_qty: dict[tuple[str, str], float] = {k: max(sells_qty.get(k, 0.0), gl_closures.get(k, 0.0)) for k in keys}

    # Group equity lots by (account, ticker), oldest first; preserve original order
    # so the returned list matches input order on lot identity.
    grouped: dict[tuple[str, str], list[Lot]] = defaultdict(list)
    for lot in lots_list:
        if lot.option_details is not None:
            continue
        grouped[(lot.account, lot.ticker)].append(lot)
    for group in grouped.values():
        group.sort(key=lambda lt: lt.date)

    remaining: dict[str, tuple[Decimal, Decimal]] = {}  # lot.id -> (qty, basis)
    for lot in lots_list:
        remaining[lot.id] = (Decimal(str(lot.quantity)), Decimal(str(lot.adjusted_basis)))

    for key, group in grouped.items():
        to_consume = Decimal(str(closed_qty.get(key, 0.0)))
        for lot in group:
            if to_consume <= 0:
                break
            lot_qty, lot_basis = remaining[lot.id]
            if lot_qty <= 0:
                continue
            take = min(lot_qty, to_consume)
            ratio = take / lot_qty
            new_qty = lot_qty - take
            new_basis = lot_basis - (lot_basis * ratio)
            remaining[lot.id] = (new_qty, new_basis)
            to_consume -= take

    return [(lot, *remaining[lot.id]) for lot in lots_list]


def compute_open_positions(
    *,
    trades: Iterable[Trade],
    lots: Iterable[Lot],
    prices: dict[str, Quote],
    period: tuple[int, int] | None = None,  # (year_start, year_end_exclusive); None = all time
    account: str | None = None,
    include_closed: bool = False,
    gl_closures: dict[tuple[str, str], float] | None = None,
) -> list[PositionRow]:
    """Return positions sorted by market value desc (None last).

    When ``include_closed`` is True, also include symbols that have no open
    quantity but had Sell activity in the period — useful for "All" table mode
    where the user wants to see realized P/L on positions they've fully exited.
    """
    trades = list(trades)
    lots = list(lots)

    # Account scope
    if account:
        trades = [t for t in trades if t.account == account]
        lots = [lot for lot in lots if lot.account == account]
        gl_closures = {k: v for k, v in (gl_closures or {}).items() if k[0] == account} if gl_closures else None

    consumed = consume_lots_fifo(lots=lots, trades=trades, gl_closures=gl_closures)

    # Aggregate equity-only quantities and basis from FIFO-reduced lots.
    qty_by_sym: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    open_cost_by_sym: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    accounts_by_sym: dict[str, set[str]] = defaultdict(set)
    for lot, rem_qty, rem_basis in consumed:
        if lot.option_details is not None:
            continue
        if rem_qty <= 0:
            continue
        qty_by_sym[lot.ticker] += rem_qty
        open_cost_by_sym[lot.ticker] += rem_basis
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
    if include_closed:
        seen = {r.symbol for r in rows}
        # Closed symbols: had Sell activity (period-scoped if a period is set)
        # but no remaining open quantity.
        for sym, realized in realized_by_sym.items():
            if sym in seen:
                continue
            if qty_by_sym.get(sym, Decimal("0")) != 0:
                continue
            rows.append(
                PositionRow(
                    symbol=sym,
                    accounts=tuple(sorted(accounts_by_sym[sym])),
                    qty=Decimal("0"),
                    market_value=Decimal("0"),
                    open_cost=Decimal("0"),
                    avg_basis=Decimal("0"),
                    cash_sunk_per_share=Decimal("0"),
                    realized_pl=realized,
                    unrealized_pl=Decimal("0"),
                )
            )
    rows.sort(key=lambda r: (r.market_value is None, -(r.market_value or Decimal("0"))))
    return rows
