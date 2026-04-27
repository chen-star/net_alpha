"""Recent-loss-close aggregation for the home-page wash-sale watch panel.

Surfaces sell trades with negative realized P/L closed in the last N days,
collapsed to one row per symbol (most recent close, summed loss). The UI uses
this to remind the user "don't buy these back yet — wash sale window still
open."

Pure function; no DB/IO of its own. The repo dependency is a duck-typed object
that exposes `.all_trades()` returning an iterable of Trade.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any, Protocol

from net_alpha.portfolio.models import LossCloseRow


class _RepoLike(Protocol):
    def all_trades(self) -> Iterable[Any]: ...


def recent_loss_closes(
    *,
    repo: _RepoLike,
    today: date,
    window_days: int = 30,
    account: str | None = None,
) -> list[LossCloseRow]:
    """Sells with realized P/L < 0 whose close_date is in [today - window_days, today].

    Grouped by symbol — if a symbol has multiple loss closes in window, the row
    uses the most recent date and account, and the loss_amount is the sum of
    |negative realized P/L| across all loss closes for that symbol in window.

    `today` is the server-side `date.today()` at request time — no caching of
    "today" across HTMX swaps. `days_to_safe = max(0, window_days - days_since)`.

    Returns rows sorted by close_date desc.
    """
    earliest = date.fromordinal(today.toordinal() - window_days)

    by_symbol: dict[str, list[tuple[date, str, Decimal]]] = defaultdict(list)
    for t in repo.all_trades():
        if t.action.lower() != "sell":
            continue
        if t.date < earliest or t.date > today:
            continue
        proceeds = Decimal(str(t.proceeds or 0))
        basis = Decimal(str(t.cost_basis or 0))
        pl = proceeds - basis
        if pl >= 0:
            continue
        if account and t.account != account:
            continue
        by_symbol[t.ticker].append((t.date, t.account, -pl))  # store loss as positive

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
