"""Pure function: build a SPY (or other symbol) benchmark shadow-account
series aligned with a list of evaluation dates.

The shadow account simulates 'put my real cash flows into the index instead'.
Each contribution buys fractional shares at that day's close; each withdrawal
sells pro-rata. Output is one BenchmarkPoint per requested evaluation date.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal

from net_alpha.portfolio.models import BenchmarkPoint, CashBalancePoint

# Forward-fill window for contributions that land on a non-trading day
# (weekend or holiday). 5 calendar days covers Saturday-evening cash
# settling against the next trading day after a Monday holiday (e.g.
# MLK Day, Memorial Day) without needing a real exchange calendar.
_FWD_FILL_MAX_DAYS = 5


def _close_with_fwd_fill(
    symbol: str,
    cd: date,
    get_close: Callable[[str, date], Decimal | None],
    *,
    max_days: int = _FWD_FILL_MAX_DAYS,
) -> Decimal | None:
    """Return ``get_close(symbol, cd)`` if available, else probe forward up
    to ``max_days`` calendar days for the next trading-day close.

    Audit #37: contributions landing on a weekend / holiday previously
    bought zero benchmark shares because the close was None on that date,
    permanently losing the cash from the shadow series. Forward-filling
    to the next trading day mirrors how a brokerage would settle the
    deposit at the next available execution price.
    """
    close = get_close(symbol, cd)
    if close is not None:
        return close
    for offset in range(1, max_days + 1):
        probe = cd + timedelta(days=offset)
        close = get_close(symbol, probe)
        if close is not None:
            return close
    return None


def build_benchmark_series(
    *,
    symbol: str,
    eq_dates: list[date],
    cash_points: list[CashBalancePoint],
    get_close: Callable[[str, date], Decimal | None],
) -> list[BenchmarkPoint]:
    """Return one BenchmarkPoint per date in eq_dates.

    Args:
        symbol: benchmark symbol (e.g. "SPY")
        eq_dates: dates at which to evaluate the shadow value (typically the
                  AccountValuePoint date axis)
        cash_points: cumulative contribution series (must be sorted by date asc;
                     CashBalancePoint.cumulative_contributions is the basis)
        get_close: callable returning the close on a given date or None

    Contributions landing on a non-trading day (weekend / holiday) forward-
    fill to the next trading-day close within a 5-calendar-day window. If
    no close is available within that window, the contribution is silently
    skipped (defensive fallback for users whose quote history is sparse).
    """
    if not cash_points:
        return []

    # Build (date, contribution_delta) walk from the cumulative series.
    deltas: list[tuple[date, Decimal]] = []
    prior = Decimal("0")
    for cp in sorted(cash_points, key=lambda p: p.on):
        delta = cp.cumulative_contributions - prior
        if delta != Decimal("0"):
            deltas.append((cp.on, delta))
            prior = cp.cumulative_contributions

    # Walk eq_dates, applying each contribution as it falls before/on the date.
    series: list[BenchmarkPoint] = []
    shares = Decimal("0")
    delta_i = 0
    for d in sorted(eq_dates):
        # Apply all deltas with date <= d that haven't been applied yet.
        while delta_i < len(deltas) and deltas[delta_i][0] <= d:
            cd, amount = deltas[delta_i]
            close = _close_with_fwd_fill(symbol, cd, get_close)
            if close is not None and close != Decimal("0"):
                shares += amount / close
            delta_i += 1
        close_today = get_close(symbol, d)
        if close_today is None:
            series.append(BenchmarkPoint(on=d, value=None))
        else:
            value = (shares * close_today).quantize(Decimal("0.01"))
            series.append(BenchmarkPoint(on=d, value=value))
    return series
