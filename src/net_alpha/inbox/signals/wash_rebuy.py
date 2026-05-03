"""Wash safe-to-rebuy signal — H2.

For each WashSaleViolation, emit an InboxItem starting on day 31 after the
loss sale date and continuing for ``visible_days`` days afterward. Pure
function over ``repo.all_violations()``.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Protocol

from net_alpha.inbox.models import InboxItem, Severity, SignalType

WASH_WINDOW_DAYS = 31
DEFAULT_VISIBLE_DAYS = 14


class _RepoLike(Protocol):
    def all_violations(self) -> Iterable[Any]: ...


def compute_wash_rebuy(
    *,
    repo: _RepoLike,
    today: date,
    visible_days: int = DEFAULT_VISIBLE_DAYS,
    account: str | None = None,
) -> list[InboxItem]:
    items: list[InboxItem] = []
    for v in repo.all_violations():
        if v.loss_sale_date is None:
            continue
        if account and v.loss_account != account and v.buy_account != account:
            continue
        safe_date = v.loss_sale_date + timedelta(days=WASH_WINDOW_DAYS)
        if today < safe_date:
            continue
        days_past = (today - safe_date).days
        if days_past > visible_days:
            continue
        if days_past == 0:
            subtitle = f"Wash window cleared today — disallowed loss was ${v.disallowed_loss:.0f}"
        elif days_past == 1:
            subtitle = f"Wash window cleared 1 day ago — disallowed loss was ${v.disallowed_loss:.0f}"
        else:
            subtitle = f"Wash window cleared {days_past} days ago — disallowed loss was ${v.disallowed_loss:.0f}"
        items.append(
            InboxItem(
                signal_type=SignalType.WASH_REBUY,
                dismiss_key=f"wash_rebuy:{v.id}",
                ticker=v.ticker,
                title=f"{v.ticker} safe to rebuy",
                subtitle=subtitle,
                event_date=safe_date,
                days_until=-days_past,
                dollar_impact=Decimal(str(v.disallowed_loss)),
                severity=Severity.INFO,
                deep_link=f"/sim?action=buy&ticker={v.ticker}",
            )
        )
    return items
