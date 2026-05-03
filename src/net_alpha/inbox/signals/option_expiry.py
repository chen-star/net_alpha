"""Option expiration (O2) and assignment risk (O4) signals.

Both signals walk open option lots from ``repo.all_lots()``. The expiry
signal emits one item per qualifying lot. The assignment-risk signal
emits a SEPARATE item alongside (not replacing) the expiry item when the
lot is short, ITM, and inside the assignment-risk window.

Long lots never produce assignment-risk items.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any, Protocol

from net_alpha.inbox.models import InboxItem, Severity, SignalType

OPTION_MULTIPLIER = Decimal("100")
DEFAULT_EXPIRY_LOOKAHEAD_DAYS = 14
DEFAULT_ASSIGNMENT_WINDOW_DAYS = 7
URGENT_DAYS = 1
WATCH_DAYS = 7


class _RepoLike(Protocol):
    def all_lots(self) -> Iterable[Any]: ...


class _PricesLike(Protocol):
    def get_prices(self, symbols: list[str]) -> dict[str, Any]: ...


def _expiry_severity(days_until: int) -> Severity:
    if days_until <= URGENT_DAYS:
        return Severity.URGENT
    if days_until <= WATCH_DAYS:
        return Severity.WATCH
    return Severity.INFO


def _expiry_subtitle(days_until: int) -> str:
    if days_until == 0:
        return "expires today"
    if days_until == 1:
        return "1d left"
    return f"{days_until}d left"


def _is_itm(*, call_put: str, underlying: Decimal, strike: Decimal) -> bool:
    if call_put.upper() == "C":
        return underlying >= strike
    return underlying <= strike


def compute_option_expiry(
    *,
    repo: _RepoLike,
    prices: _PricesLike,
    today: date,
    expiry_lookahead_days: int = DEFAULT_EXPIRY_LOOKAHEAD_DAYS,
    assignment_window_days: int = DEFAULT_ASSIGNMENT_WINDOW_DAYS,
    account: str | None = None,
) -> list[InboxItem]:
    open_option_lots = [
        lot
        for lot in repo.all_lots()
        if lot.option_details is not None and (account is None or lot.account == account) and lot.quantity != 0
    ]
    if not open_option_lots:
        return []

    underlying_tickers = sorted({lot.ticker for lot in open_option_lots})
    quotes = prices.get_prices(underlying_tickers)

    items: list[InboxItem] = []
    for lot in open_option_lots:
        opt = lot.option_details
        days_until = (opt.expiry - today).days
        if days_until < 0 or days_until > expiry_lookahead_days:
            continue

        strike = Decimal(str(opt.strike))
        cp = opt.call_put.upper()
        contracts = abs(Decimal(str(lot.quantity)))
        is_short = lot.quantity < 0

        quote = quotes.get(lot.ticker)
        underlying_price: Decimal | None = None
        if quote is not None:
            underlying_price = Decimal(str(quote.price))

        # OPTION_EXPIRY (always emitted for in-window lots).
        # Use intrinsic value × multiplier × contracts as a stable, no-options-API
        # estimate of dollars on the table. None when no underlying quote.
        market_value: Decimal | None = None
        if underlying_price is not None:
            intrinsic = max(
                Decimal("0"),
                underlying_price - strike if cp == "C" else strike - underlying_price,
            )
            market_value = intrinsic * OPTION_MULTIPLIER * contracts

        items.append(
            InboxItem(
                signal_type=SignalType.OPTION_EXPIRY,
                dismiss_key=f"option_expiry:{lot.trade_id}",
                ticker=lot.ticker,
                title=f"{lot.ticker} {opt.strike:g}{cp} exp {opt.expiry.isoformat()}",
                subtitle=_expiry_subtitle(days_until),
                event_date=opt.expiry,
                days_until=days_until,
                dollar_impact=market_value,
                severity=_expiry_severity(days_until),
                deep_link=f"/ticker/{lot.ticker}",
                # extras: read by the panel template (Task 10) for chip styling and
                # the "long/short" badge — keep keys stable.
                extras={"is_short": is_short, "strike": float(strike), "call_put": cp},
            )
        )

        # ASSIGNMENT_RISK (only short, ITM, inside assignment window, with quote)
        if (
            is_short
            and days_until <= assignment_window_days
            and underlying_price is not None
            and _is_itm(call_put=cp, underlying=underlying_price, strike=strike)
        ):
            itm_amount = (
                ((underlying_price - strike) if cp == "C" else (strike - underlying_price))
                * contracts
                * OPTION_MULTIPLIER
            )
            items.append(
                InboxItem(
                    signal_type=SignalType.ASSIGNMENT_RISK,
                    dismiss_key=f"assignment_risk:{lot.trade_id}",
                    ticker=lot.ticker,
                    title=f"{lot.ticker} {opt.strike:g}{cp} assignment risk",
                    subtitle=f"${itm_amount:.0f} ITM, expires {opt.expiry.isoformat()}",
                    event_date=opt.expiry,
                    days_until=days_until,
                    dollar_impact=itm_amount,
                    severity=Severity.URGENT,
                    deep_link=f"/ticker/{lot.ticker}",
                    extras={
                        "itm_amount": float(itm_amount),
                        "underlying_price": float(underlying_price),
                    },
                )
            )
    return items
