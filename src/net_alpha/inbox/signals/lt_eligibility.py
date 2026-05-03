"""Long-term eligibility signal — H3.

For each open Lot whose 1-year holding threshold falls inside the
lookahead window (and has positive unrealized gain), emit an InboxItem
showing how much extra short-term tax selling now would cost.

Pure function. ``prices`` is the project's PricingService — only
``get_prices(symbols)`` is used, so test stubs need only that method.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Protocol

from net_alpha.inbox.models import InboxItem, Severity, SignalType

LT_HOLDING_DAYS = 366  # IRS: holding period must be MORE than one year
DEFAULT_LOOKAHEAD_DAYS = 60
WATCH_THRESHOLD_DAYS = 14


class _RepoLike(Protocol):
    def all_lots(self) -> Iterable[Any]: ...


class _PricesLike(Protocol):
    def get_prices(self, symbols: list[str]) -> dict[str, Any]: ...


def compute_lt_eligibility(
    *,
    repo: _RepoLike,
    prices: _PricesLike,
    today: date,
    st_rate: Decimal,
    lt_rate: Decimal,
    lookahead_days: int = DEFAULT_LOOKAHEAD_DAYS,
    account: str | None = None,
) -> list[InboxItem]:
    open_equity_lots = [
        lot
        for lot in repo.all_lots()
        if lot.option_details is None and (account is None or lot.account == account) and lot.quantity > 0
    ]
    if not open_equity_lots:
        return []

    # Bulk fetch quotes once for all relevant tickers.
    tickers = sorted({lot.ticker for lot in open_equity_lots})
    quotes = prices.get_prices(tickers)

    rate_delta = st_rate - lt_rate

    items: list[InboxItem] = []
    for lot in open_equity_lots:
        lt_date = lot.date + timedelta(days=LT_HOLDING_DAYS)
        days_until = (lt_date - today).days
        if days_until <= 0 or days_until > lookahead_days:
            continue

        quote = quotes.get(lot.ticker)
        cost_of_st: Decimal | None = None
        if quote is not None and getattr(quote, "price", None) is not None:
            current_price = Decimal(str(quote.price))
            unrealized = (current_price * Decimal(str(lot.quantity))) - Decimal(str(lot.adjusted_basis))
            if unrealized <= 0:
                continue
            cost_of_st = unrealized * rate_delta

        qty_int = int(lot.quantity) if float(lot.quantity).is_integer() else lot.quantity
        if cost_of_st is not None:
            subtitle = f"{qty_int} sh acquired {lot.date.isoformat()} — selling now costs +${cost_of_st:.0f} in tax"
        else:
            subtitle = f"{qty_int} sh acquired {lot.date.isoformat()} (no price)"

        items.append(
            InboxItem(
                signal_type=SignalType.LT_ELIGIBLE,
                dismiss_key=f"lt_eligible:{lot.id}",
                ticker=lot.ticker,
                title=f"{lot.ticker} LT in {days_until}d",
                subtitle=subtitle,
                event_date=lt_date,
                days_until=days_until,
                dollar_impact=cost_of_st,
                severity=Severity.WATCH if days_until <= WATCH_THRESHOLD_DAYS else Severity.INFO,
                deep_link=f"/ticker/{lot.ticker}?lot={lot.id}",
            )
        )
    return items
