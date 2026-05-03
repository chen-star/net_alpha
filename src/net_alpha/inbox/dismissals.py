"""Persistence helpers for inbox item dismissals.

A dismissal is a single row in dismissed_inbox_items keyed by the
namespaced dismiss_key (e.g. ``wash_rebuy:42``). Toggle is the only
mutation; reads happen via apply_dismissals() during aggregation, and
orphan rows are pruned by sweep_orphans().

Timestamps are written in UTC ISO 8601 to match the convention on the
other timestamp-as-str columns in db/tables.py.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import text
from sqlmodel import Session

from net_alpha.inbox.models import InboxItem


def is_dismissed(session: Session, dismiss_key: str) -> bool:
    row = session.exec(
        text("SELECT 1 FROM dismissed_inbox_items WHERE dismiss_key = :k"),
        params={"k": dismiss_key},
    ).first()
    return row is not None


def toggle_dismissal(session: Session, dismiss_key: str) -> bool:
    """Toggle dismissal state. Returns True if now dismissed, False if cleared."""
    if is_dismissed(session, dismiss_key):
        session.exec(
            text("DELETE FROM dismissed_inbox_items WHERE dismiss_key = :k"),
            params={"k": dismiss_key},
        )
        session.commit()
        return False
    session.exec(
        text("INSERT INTO dismissed_inbox_items (dismiss_key, dismissed_at) VALUES (:k, :ts)"),
        params={"k": dismiss_key, "ts": datetime.now(UTC).isoformat()},
    )
    session.commit()
    return True


def _all_dismissed_keys(session: Session) -> set[str]:
    rows = session.exec(text("SELECT dismiss_key FROM dismissed_inbox_items")).all()
    return {r[0] for r in rows}


def apply_dismissals(session: Session, items: list[InboxItem]) -> list[InboxItem]:
    if not items:
        return items
    dismissed = _all_dismissed_keys(session)
    if not dismissed:
        return items
    return [i for i in items if i.dismiss_key not in dismissed]


def sweep_orphans(session: Session, live_keys: Iterable[str]) -> int:
    """Delete dismissal rows whose key is not in ``live_keys``. Returns count deleted."""
    live_set = set(live_keys)
    dismissed = _all_dismissed_keys(session)
    orphans = dismissed - live_set
    if not orphans:
        return 0
    for k in orphans:
        session.exec(
            text("DELETE FROM dismissed_inbox_items WHERE dismiss_key = :k"),
            params={"k": k},
        )
    session.commit()
    return len(orphans)
