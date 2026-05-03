"""Combine all signals, apply dismissals, sweep orphans, and sort.

This is the only function the web layer calls. Pure-ish — the only side
effect is the orphan sweep (DELETE from dismissed_inbox_items for keys
that no longer have a live signal).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Protocol

from sqlmodel import Session

from net_alpha.inbox.config import InboxConfig
from net_alpha.inbox.dismissals import apply_dismissals, sweep_orphans
from net_alpha.inbox.models import InboxItem, Severity
from net_alpha.inbox.signals.lt_eligibility import compute_lt_eligibility
from net_alpha.inbox.signals.option_expiry import compute_option_expiry
from net_alpha.inbox.signals.wash_rebuy import compute_wash_rebuy

_SEVERITY_RANK = {Severity.URGENT: 0, Severity.WATCH: 1, Severity.INFO: 2}


class _RepoLike(Protocol):
    def all_violations(self) -> Any: ...

    def all_lots(self) -> Any: ...


class _PricesLike(Protocol):
    def get_prices(self, symbols: list[str]) -> dict[str, Any]: ...


def _sort_key(item: InboxItem) -> tuple[int, int, Decimal]:
    dollars = item.dollar_impact if item.dollar_impact is not None else Decimal("0")
    return (_SEVERITY_RANK[item.severity], abs(item.days_until), -abs(dollars))


def gather_inbox(
    *,
    repo: _RepoLike,
    prices: _PricesLike,
    session: Session,
    today: date,
    config: InboxConfig,
    st_rate: Decimal,
    lt_rate: Decimal,
    account: str | None = None,
) -> list[InboxItem]:
    raw: list[InboxItem] = []
    raw.extend(
        compute_wash_rebuy(
            repo=repo,
            today=today,
            visible_days=config.wash_rebuy_visible_days,
            account=account,
        )
    )
    raw.extend(
        compute_lt_eligibility(
            repo=repo,
            prices=prices,
            today=today,
            st_rate=st_rate,
            lt_rate=lt_rate,
            lookahead_days=config.lt_lookahead_days,
            account=account,
        )
    )
    raw.extend(
        compute_option_expiry(
            repo=repo,
            prices=prices,
            today=today,
            expiry_lookahead_days=config.option_expiry_lookahead_days,
            assignment_window_days=config.assignment_risk_window_days,
            account=account,
        )
    )

    sweep_orphans(session, live_keys={i.dismiss_key for i in raw})
    visible = apply_dismissals(session, raw)
    visible.sort(key=_sort_key)
    return visible
