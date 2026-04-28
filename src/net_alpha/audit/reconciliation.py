from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from net_alpha.audit.brokers.registry import get_provider_for_account
from net_alpha.db.repository import Repository

DEFAULT_TOLERANCE = 0.50


class ReconciliationStatus(StrEnum):
    MATCH = "match"
    NEAR_MATCH = "near_match"  # within tolerance
    DIFF = "diff"  # exceeds tolerance
    UNAVAILABLE = "unavailable"  # no broker provider for this account


class ReconciliationResult(BaseModel):
    symbol: str
    account_id: int
    net_alpha_total: float
    broker_total: float | None
    delta: float
    status: ReconciliationStatus
    tolerance: float
    source_label: str | None  # e.g. "Schwab Realized G/L"


def reconcile(
    *,
    symbol: str,
    account_id: int,
    repo: Repository,
    tolerance: float = DEFAULT_TOLERANCE,
) -> ReconciliationResult:
    provider = get_provider_for_account(account_id, repo)
    net_alpha_total = _net_alpha_realized(repo, account_id, symbol)

    if provider is None:
        return ReconciliationResult(
            symbol=symbol,
            account_id=account_id,
            net_alpha_total=net_alpha_total,
            broker_total=None,
            delta=0.0,
            status=ReconciliationStatus.UNAVAILABLE,
            tolerance=tolerance,
            source_label=None,
        )

    broker_lots = provider.get_lot_detail(account_id, symbol)
    broker_total = sum((lot.proceeds or 0.0) - lot.cost_basis for lot in broker_lots)
    delta = round(net_alpha_total - broker_total, 4)
    if abs(delta) < 0.005:
        status = ReconciliationStatus.MATCH
    elif abs(delta) < tolerance:
        status = ReconciliationStatus.NEAR_MATCH
    else:
        status = ReconciliationStatus.DIFF

    source_label = broker_lots[0].source_label if broker_lots else None
    return ReconciliationResult(
        symbol=symbol,
        account_id=account_id,
        net_alpha_total=round(net_alpha_total, 2),
        broker_total=round(broker_total, 2),
        delta=delta,
        status=status,
        tolerance=tolerance,
        source_label=source_label,
    )


def _net_alpha_realized(repo: Repository, account_id: int, symbol: str) -> float:
    """Sum realized P/L for the (account, symbol) pair across all time."""
    total = 0.0
    accounts = {a.id: f"{a.broker}/{a.label}" if a.label else a.broker for a in repo.list_accounts()}
    target_display = accounts.get(account_id)
    for t in repo.get_trades_for_ticker(symbol):
        if t.action.lower() != "sell":
            continue
        if target_display is not None and t.account != target_display:
            continue
        total += (t.proceeds or 0.0) - (t.cost_basis or 0.0)
    return total
