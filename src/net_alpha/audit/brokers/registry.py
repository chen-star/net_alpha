from __future__ import annotations

from net_alpha.audit.brokers.base import BrokerGLProvider
from net_alpha.audit.brokers.schwab import SchwabGLProvider
from net_alpha.db.repository import Repository


def get_provider_for_account(account_id: int, repo: Repository) -> BrokerGLProvider | None:
    """Return the first registered provider that supports ``account_id``.

    Future brokers add a candidate to ``candidates`` (in priority order). When
    no provider matches, returns ``None`` — the reconciliation strip renders
    'not available for this account' rather than implying a problem.
    """
    candidates: list[BrokerGLProvider] = [SchwabGLProvider(repo)]
    for p in candidates:
        if p.supports(account_id):
            return p
    return None
