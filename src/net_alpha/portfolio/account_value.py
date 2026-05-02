"""Pure functions for the redesigned equity curve (account value over time).

The chart anchors to a "cumulative contributions" baseline; the colored gap
between contributions and account_value is net P&L. See
``docs/superpowers/specs/2026-05-02-equity-curve-redesign-design.md``.

This module is import-safe — no I/O, no DB, no network. Callers inject a
``get_close`` callable (typically ``PricingService.get_historical_close``).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterable  # noqa: F401
from decimal import Decimal

from net_alpha.models.domain import Lot, Trade
from net_alpha.portfolio.models import CashBalancePoint  # noqa: F401  (used in later tasks)
from net_alpha.portfolio.positions import consume_lots_fifo


def build_eval_dates(
    *,
    period: tuple[int, int] | None,
    today: dt.date,
    event_dates: Iterable[dt.date],
) -> list[dt.date]:
    """Build the ordered, deduplicated list of dates to evaluate.

    - period=(y, y+1)  → year-scoped: weekly Fridays from Jan 1 → min(Dec 31, today).
    - period=None      → lifetime: monthly (last business day) from earliest
                         event_date → today.

    Event dates (trade and cash-event dates inside the window) are always
    appended so the chart never misses a step.
    """
    events = sorted({d for d in event_dates})
    out: set[dt.date] = set()

    if period is not None:
        year_start = dt.date(period[0], 1, 1)
        year_end_excl = dt.date(period[1], 1, 1)
        last = min(year_end_excl - dt.timedelta(days=1), today)
        # Weekly: every Friday from year_start..last (inclusive).
        first_friday = year_start + dt.timedelta(days=(4 - year_start.weekday()) % 7)
        d = first_friday
        while d <= last:
            out.add(d)
            d += dt.timedelta(days=7)
        out.add(last)  # ensure trailing point
        # Event dates inside the window
        for ed in events:
            if year_start <= ed <= last:
                out.add(ed)
    else:
        if not events:
            return []
        start = events[0]
        # Monthly: walk month-by-month, taking the last calendar day of each
        # completed month between start and today.
        cur = dt.date(start.year, start.month, 1)
        while cur <= today:
            # Last day of month: jump to first of next month, subtract 1 day.
            if cur.month == 12:
                next_first = dt.date(cur.year + 1, 1, 1)
            else:
                next_first = dt.date(cur.year, cur.month + 1, 1)
            last_of_month = next_first - dt.timedelta(days=1)
            if start <= last_of_month <= today:
                out.add(last_of_month)
            cur = next_first
        out.add(start)
        out.add(today)
        for ed in events:
            if start <= ed <= today:
                out.add(ed)

    return sorted(out)


_FORWARD_FILL_DAYS = 7


def _close_with_forward_fill(
    *,
    ticker: str,
    on: dt.date,
    get_close: Callable[[str, dt.date], Decimal | None],
) -> Decimal | None:
    """Try ``on`` first, then walk back up to 7 calendar days for a known close."""
    for offset in range(_FORWARD_FILL_DAYS + 1):
        d = on - dt.timedelta(days=offset)
        c = get_close(ticker, d)
        if c is not None:
            return c
    return None


def holdings_value_at(
    *,
    on: dt.date,
    trades: list[Trade],
    lots: list[Lot],
    get_close: Callable[[str, dt.date], Decimal | None],
) -> tuple[Decimal | None, tuple[str, ...]]:
    """Compute marked-to-market value of currently-open lots as of ``on``.

    Returns ``(value, missing_tickers)``.
    - Equity lots: rem_qty × close(ticker, on), with up-to-7-day forward fill.
    - Option lots: rem_basis (carry at basis — see spec rationale).
    - If any equity lot's close is missing after forward-fill, ``value`` is None
      and the offending ticker is included in ``missing_tickers``.
    - Lots not yet acquired (lot.date > on) and trades after ``on`` are ignored.
    """
    trades_asof = [t for t in trades if t.date <= on]
    lots_asof = [lt for lt in lots if lt.date <= on]
    consumed = consume_lots_fifo(lots=lots_asof, trades=trades_asof)

    total = Decimal("0")
    missing: list[str] = []
    any_missing = False
    for lot, rem_qty, rem_basis in consumed:
        if rem_qty <= 0:
            continue
        if lot.option_details is not None:
            total += rem_basis
            continue
        close = _close_with_forward_fill(ticker=lot.ticker, on=on, get_close=get_close)
        if close is None:
            any_missing = True
            if lot.ticker not in missing:
                missing.append(lot.ticker)
            continue
        total += (rem_qty * close).quantize(Decimal("0.01"))

    if any_missing:
        return None, tuple(missing)
    return total, ()
