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
from types import SimpleNamespace
from typing import Any, Protocol

from net_alpha.inbox.models import InboxItem, Severity, SignalType
from net_alpha.models.domain import OptionDetails
from net_alpha.portfolio.positions import compute_open_short_option_positions, open_lots_view

OPTION_MULTIPLIER = Decimal("100")
DEFAULT_EXPIRY_LOOKAHEAD_DAYS = 14
DEFAULT_ASSIGNMENT_WINDOW_DAYS = 7
URGENT_DAYS = 1
WATCH_DAYS = 7


class _RepoLike(Protocol):
    def all_lots(self) -> Iterable[Any]: ...

    def all_trades(self) -> Iterable[Any]: ...

    def get_option_gl_closures(
        self,
    ) -> dict[tuple[str, str, float, str, str], float]: ...


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


def _build_short_lot_views(repo: _RepoLike, *, trades: list[Any]) -> list[Any]:
    """Synthesize lot-shaped rows for open short option chains.

    STO never creates a Lot, so short positions only exist as STO/BTC trade
    pairs. Reuse the portfolio's net-by-chain aggregator and present each
    open chain as a Lot-like object the emission loop can consume. The
    synthetic ``trade_id`` encodes the chain key so the resulting
    ``option_expiry:`` / ``assignment_risk:`` dismiss_keys stay stable
    across re-runs.
    """
    gl_getter = getattr(repo, "get_option_gl_closures", None)
    gl_closures: dict[Any, float] | None
    try:
        gl_closures = gl_getter() if callable(gl_getter) else None
    except Exception:
        gl_closures = None
    if not isinstance(gl_closures, dict):
        gl_closures = None
    rows = compute_open_short_option_positions(trades, gl_option_closures=gl_closures)
    out: list[Any] = []
    for r in rows:
        chain_id = f"short:{r.account}:{r.ticker}:{r.strike}:{r.expiry.isoformat()}:{r.call_put}"
        out.append(
            SimpleNamespace(
                trade_id=chain_id,
                account=r.account,
                ticker=r.ticker,
                quantity=-float(r.qty_short),
                option_details=OptionDetails(strike=r.strike, expiry=r.expiry, call_put=r.call_put),
            )
        )
    return out


def compute_option_expiry(
    *,
    repo: _RepoLike,
    prices: _PricesLike,
    today: date,
    expiry_lookahead_days: int = DEFAULT_EXPIRY_LOOKAHEAD_DAYS,
    assignment_window_days: int = DEFAULT_ASSIGNMENT_WINDOW_DAYS,
    account: str | None = None,
) -> list[InboxItem]:
    # FIFO-net lots against trades so options the user has STC'd no longer
    # appear. The detector only ever creates lots for buys, so a closed-out
    # long-call lot keeps its original positive quantity in the DB —
    # `repo.all_lots()` alone treats it as still open. (See WULF 23C bug.)
    # `open_lots_view` drops rem_qty <= 0, which includes negative-quantity
    # short lots that consumption never touches; preserve them since shorts
    # aren't netted via FIFO in this codebase (STO doesn't create a lot).
    raw_lots = list(repo.all_lots())
    trades = list(repo.all_trades())
    consumed_lots = list(open_lots_view(lots=raw_lots, trades=trades))
    # The detector only creates Lots for Buys, so STO short positions never
    # appear in `repo.all_lots()`. Reconstruct them from the trade table the
    # same way the portfolio's open-shorts panel does, so near-expiring CSPs
    # and covered calls reach the inbox.
    short_lots_from_trades = _build_short_lot_views(repo, trades=trades)
    # Legacy: tests fabricate negative-quantity Lot rows to exercise short
    # behavior. Production never produces them, but keeping this preserves
    # those tests as additional coverage of the same code path below.
    short_lots = [lot for lot in raw_lots if lot.quantity < 0]
    open_option_lots = [
        lot
        for lot in consumed_lots + short_lots + short_lots_from_trades
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
