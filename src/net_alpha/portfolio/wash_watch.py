"""Recent-loss-close aggregation for the home-page wash-sale watch panel.

Surfaces realized loss closes (equity sells AND short-option Buy-to-Close
trades) from the last N days, collapsed to one row per symbol. The UI
uses this to remind the user "don't buy these back yet — wash sale window
still open."

Pure function; no DB/IO of its own. The repo dependency is a duck-typed object
that exposes `.all_trades()` returning an iterable of Trade.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date
from decimal import Decimal
from typing import Any, Protocol

from net_alpha.portfolio.models import LossCloseRow
from net_alpha.portfolio.pnl import realized_pl_contributions


class _RepoLike(Protocol):
    def all_trades(self) -> Iterable[Any]: ...


def recent_loss_closes(
    *,
    repo: _RepoLike,
    today: date,
    window_days: int = 30,
    accounts: Sequence[str] | None = None,
) -> list[LossCloseRow]:
    """Realized closes with P/L < 0 whose close date is in
    [today - window_days, today].

    Includes both equity Sells AND short-option Buy-to-Close (BTC) trades
    — closing a short option at a loss creates the same §1091 30-day
    lockout risk as closing an equity at a loss, so the user needs the
    same warning.

    Grouped by symbol — if a symbol has multiple loss closes in window, the
    row uses the most recent date and account, and the loss_amount is the
    sum of |negative realized P/L| across all loss closes for that symbol
    in window.

    `today` is the server-side `date.today()` at request time — no caching
    of "today" across HTMX swaps.
    `days_to_safe = max(0, window_days - days_since)`.

    Returns rows sorted by close_date desc.
    """
    _filter = set(accounts) if accounts else None
    earliest = date.fromordinal(today.toordinal() - window_days)

    # ``realized_pl_contributions`` handles STO/BTC pairing so a BTC's
    # contribution is ``premium_share - btc.cost_basis`` rather than the
    # raw ``-cost_basis`` we'd get if we mis-treated BTC as a sell.
    contributions = realized_pl_contributions(repo.all_trades(), period=None)

    by_symbol: dict[str, list[tuple[date, str, Decimal]]] = defaultdict(list)
    for c in contributions:
        if c.date < earliest or c.date > today:
            continue
        if c.amount >= 0:
            continue
        if _filter is not None and c.account not in _filter:
            continue
        by_symbol[c.ticker].append((c.date, c.account, -c.amount))

    rows: list[LossCloseRow] = []
    for symbol, entries in by_symbol.items():
        entries.sort(key=lambda e: e[0], reverse=True)
        most_recent_date, most_recent_account, _ = entries[0]
        loss_total = sum((loss for _, _, loss in entries), start=Decimal("0"))
        days_since = (today - most_recent_date).days
        days_to_safe = max(0, window_days - days_since)
        rows.append(
            LossCloseRow(
                symbol=symbol,
                account=most_recent_account,
                close_date=most_recent_date,
                days_since=days_since,
                days_to_safe=days_to_safe,
                loss_amount=loss_total,
            )
        )

    rows.sort(key=lambda r: r.close_date, reverse=True)
    return rows
