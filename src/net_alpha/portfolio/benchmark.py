"""Pure function: build a SPY (or other symbol) benchmark shadow-account
series aligned with a list of evaluation dates.

The shadow account simulates 'put my real cash flows into the index instead'.
Each contribution buys fractional shares at that day's close; each withdrawal
sells pro-rata. Output is one BenchmarkPoint per requested evaluation date.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

from net_alpha.portfolio.models import BenchmarkPoint, CashBalancePoint


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
            close = get_close(symbol, cd)
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
