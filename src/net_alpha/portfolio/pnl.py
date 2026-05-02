"""KPI aggregations for the Portfolio page header.

period: (year_start_inclusive, year_end_exclusive), e.g. (2026, 2027) for YTD 2026,
or None for "Lifetime" (no period filter).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal

from net_alpha.models.domain import Lot, Trade, WashSaleViolation
from net_alpha.portfolio.models import KpiSet, WashImpact
from net_alpha.portfolio.positions import compute_today_change
from net_alpha.pricing.provider import Quote

# BTC basis_source values whose realization pairs with a matching STO. Excludes
# ``option_short_close_assigned`` because that flow folds the STO premium into
# the assigned long-stock basis — counting it again here would double-credit
# the user.
_BTC_REALIZE_SOURCES = frozenset({"option_short_close", "option_short_close_expiry"})

# STO sources whose premium is the proceeds side of a short. The "_assigned"
# variant is paired through the put_assignment / synthetic-close flow and
# folded into long-stock basis, so it's intentionally NOT considered for
# trade-pair realization.
_STO_PAIRABLE_SOURCES = frozenset({"option_short_open"})


def realized_pl_from_trades(trades: Iterable[Trade], period: tuple[int, int] | None) -> Decimal:
    """Sum realized P&L across a list of trades.

    Three flows are handled:

    1. **Long-lot Sells** (equity sales, STC of long options): realized on the
       Sell date as ``proceeds - cost_basis``. Matches the legacy behavior.

    2. **Short-option STO**: an open event — premium is *not* realized until
       the position closes. STOs contribute zero on their own row.

    3. **Short-option BTC** (``option_short_close`` / ``..._expiry``): paired
       with the matching STO(s) on (account, ticker, strike, expiry, call_put).
       Premium is **distributed by contract quantity** across the BTCs that
       close it: ``premium_share = total_STO_premium × btc_qty / total_STO_qty``.
       Realized at the BTC = ``premium_share − btc.cost_basis``. Without the
       quantity scaling, two 1-contract BTCs closing a 2-contract STO would
       each credit the full premium and double-count it.

    The previous implementation summed ``proceeds - cost_basis`` for every
    Sell, which counted the STO premium as realized at open and silently
    dropped the BTC close (which is a Buy). This led to inflated and
    direction-wrong YTD/lifetime realized values for any account that wrote
    options.
    """
    trades = list(trades)
    total = Decimal("0")

    sto_premium: dict[tuple, Decimal] = defaultdict(lambda: Decimal("0"))
    sto_qty: dict[tuple, Decimal] = defaultdict(lambda: Decimal("0"))
    for t in trades:
        if not t.is_sell():
            continue
        if t.basis_source not in _STO_PAIRABLE_SOURCES:
            continue
        if t.option_details is None:
            continue
        opt = t.option_details
        key = (t.account, t.ticker, opt.strike, opt.expiry, opt.call_put)
        sto_premium[key] += Decimal(str(t.proceeds or 0))
        sto_qty[key] += Decimal(str(t.quantity))

    for t in trades:
        if t.is_sell():
            # STOs and the assigned-STO variant are *not* realized at open —
            # their realization is folded into the matching close (BTC, expiry
            # synth, or rolled into stock basis on assignment).
            if t.basis_source.startswith("option_short_open"):
                continue
            if period is not None and not (period[0] <= t.date.year < period[1]):
                continue
            total += Decimal(str((t.proceeds or 0) - (t.cost_basis or 0)))
        elif t.is_buy():
            if t.basis_source not in _BTC_REALIZE_SOURCES:
                continue
            if t.option_details is None:
                continue
            opt = t.option_details
            key = (t.account, t.ticker, opt.strike, opt.expiry, opt.call_put)
            if period is not None and not (period[0] <= t.date.year < period[1]):
                continue
            total_sto_qty = sto_qty.get(key, Decimal("0"))
            btc_qty = Decimal(str(t.quantity))
            if total_sto_qty > 0:
                premium_share = sto_premium.get(key, Decimal("0")) * btc_qty / total_sto_qty
            else:
                premium_share = Decimal("0")
            total += premium_share - Decimal(str(t.cost_basis or 0))

    return total


# Backwards-compat alias: older callers in this module reference _realized_in.
_realized_in = realized_pl_from_trades


def _open_market_and_basis(
    lots: Iterable[Lot],
    prices: dict[str, Quote],
) -> tuple[Decimal, Decimal, tuple[str, ...]]:
    """Return (priced_market, priced_basis, missing_symbols).

    priced_market = Σ(qty × price) over equity lots that have a quote.
    priced_basis  = Σ(adjusted_basis) over the SAME priced lots.
    missing_symbols = sorted unique tickers we couldn't price.

    Computing both market AND basis from the same priced subset means
    ``priced_market - priced_basis`` is a correct unrealized P/L for that
    subset, even when prices for some lots are missing. Callers can then
    surface partial sums alongside a "N symbols unpriced" caveat instead
    of throwing the whole aggregate away.
    """
    total_value: Decimal = Decimal("0")
    priced_basis: Decimal = Decimal("0")
    missing: set[str] = set()
    for lot in lots:
        if lot.option_details is not None:
            continue  # equity-only for KPI market value
        quote = prices.get(lot.ticker)
        if quote is None:
            missing.add(lot.ticker)
            continue
        total_value += Decimal(str(lot.quantity)) * quote.price
        priced_basis += Decimal(str(lot.adjusted_basis))  # NOTE: adjusted_basis is total, not per-share
    return total_value, priced_basis, tuple(sorted(missing))


def compute_kpis(
    *,
    trades: Iterable[Trade],
    lots: Iterable[Lot],
    prices: dict[str, Quote],
    period_label: str,
    period: tuple[int, int] | None,
    account: str | None,
) -> KpiSet:
    trades = list(trades)
    lots = list(lots)
    if account:
        trades = [t for t in trades if t.account == account]
        lots = [lot for lot in lots if lot.account == account]

    period_realized = _realized_in(trades, period)
    lifetime_realized = _realized_in(trades, None)

    market, basis, missing = _open_market_and_basis(lots, prices)
    has_equity_lots = any(lot.option_details is None for lot in lots)
    # "All unpriced" = we have equity lots but couldn't price a single one.
    # Keep showing — in that case so users see "no data" rather than a misleading $0.
    all_unpriced = has_equity_lots and bool(missing) and market == 0 and basis == 0
    if all_unpriced:
        period_unrealized = None
        lifetime_unrealized = None
        open_value = None
        lifetime_net_pl = None
    else:
        unrealized = market - basis  # correctly scoped to priced subset
        period_unrealized = unrealized  # unrealized is "now"; period only relabels the card
        lifetime_unrealized = unrealized
        open_value = market
        lifetime_net_pl = lifetime_realized + unrealized

    # Today tile: per-lot (price - prev_close) * qty, skipping lots with no prev close.
    quotes_with_prev = {sym: (q.price, q.previous_close) for sym, q in prices.items()}
    open_lots_by_sym: list[tuple[str, Decimal]] = [
        (lot.ticker, Decimal(str(lot.quantity))) for lot in lots if lot.option_details is None
    ]
    today_change, prev_value = compute_today_change(open_lots_by_sym, quotes_with_prev)
    today_pct: Decimal | None = (today_change / prev_value) if prev_value else None

    return KpiSet(
        period_label=period_label,
        period_realized=period_realized,
        period_unrealized=period_unrealized,
        lifetime_realized=lifetime_realized,
        lifetime_unrealized=lifetime_unrealized,
        open_position_value=open_value,
        lifetime_net_pl=lifetime_net_pl,
        missing_symbols=missing,
        today_change=today_change,
        today_pct=today_pct,
    )


def compute_wash_impact(
    *,
    violations: Iterable[WashSaleViolation],
    period_label: str,
    period: tuple[int, int] | None,
    account: str | None,
) -> WashImpact:
    rows = list(violations)
    if account:
        rows = [v for v in rows if v.loss_account == account or v.buy_account == account]
    if period is not None:
        rows = [v for v in rows if v.loss_sale_date and period[0] <= v.loss_sale_date.year < period[1]]
    disallowed = sum((Decimal(str(v.disallowed_loss)) for v in rows), start=Decimal("0"))
    return WashImpact(
        period_label=period_label,
        disallowed_total=disallowed,
        violation_count=len(rows),
        confirmed_count=sum(1 for v in rows if v.confidence == "Confirmed"),
        probable_count=sum(1 for v in rows if v.confidence == "Probable"),
        unclear_count=sum(1 for v in rows if v.confidence == "Unclear"),
    )
