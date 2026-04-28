from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from net_alpha.audit.brokers.registry import get_provider_for_account
from net_alpha.db.repository import Repository
from net_alpha.models.domain import Trade

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


# ---------------------------------------------------------------------------
# Per-lot diff
# ---------------------------------------------------------------------------


class LotDiff(BaseModel):
    """One pair of (broker lot, net-alpha-derived realized) with a delta."""

    closed_date: object | None  # date | str
    opened_date: object | None
    qty: float
    broker_basis: float
    broker_proceeds: float | None
    net_alpha_basis: float | None
    net_alpha_proceeds: float | None
    delta: float
    likely_cause: str | None


def per_lot_diffs(
    *,
    symbol: str,
    account_id: int,
    repo: Repository,
) -> list[LotDiff]:
    """Pair broker G/L lots against net-alpha sell trades; return deltas with cause hints."""
    from datetime import date  # local import — avoids reshuffling top of file

    provider = get_provider_for_account(account_id, repo)
    if provider is None:
        return []
    broker_lots = provider.get_lot_detail(account_id, symbol)
    accounts = {a.id: f"{a.broker}/{a.label}" if a.label else a.broker for a in repo.list_accounts()}
    target_display = accounts.get(account_id)
    sells = [
        t
        for t in repo.get_trades_for_ticker(symbol)
        if t.action.lower() == "sell" and (target_display is None or t.account == target_display)
    ]
    sells_by_date: dict[date, Trade] = {t.date: t for t in sells}

    diffs: list[LotDiff] = []
    for bl in broker_lots:
        if bl.closed is None:
            continue
        match = sells_by_date.get(bl.closed)
        if match is None:
            diffs.append(
                LotDiff(
                    closed_date=bl.closed,
                    opened_date=bl.acquired,
                    qty=bl.qty,
                    broker_basis=bl.cost_basis,
                    broker_proceeds=bl.proceeds,
                    net_alpha_basis=None,
                    net_alpha_proceeds=None,
                    delta=0.0,
                    likely_cause="net-alpha has no matching sell on this date",
                )
            )
            continue
        na_basis = match.cost_basis or 0.0
        na_proceeds = match.proceeds or 0.0
        delta = round(
            ((na_proceeds - na_basis) - ((bl.proceeds or 0.0) - bl.cost_basis)),
            4,
        )
        diffs.append(
            LotDiff(
                closed_date=bl.closed,
                opened_date=bl.acquired,
                qty=bl.qty,
                broker_basis=bl.cost_basis,
                broker_proceeds=bl.proceeds,
                net_alpha_basis=na_basis,
                net_alpha_proceeds=na_proceeds,
                delta=delta,
                likely_cause=_cause_hint(delta, bl, match),
            )
        )
    return diffs


def _cause_hint(delta: float, bl, na: Trade) -> str | None:
    """Lightweight heuristic — rendered as 'investigate' guidance."""
    if abs(delta) < 0.005:
        return None
    if bl.proceeds is not None and na.proceeds is not None:
        if abs((na.proceeds or 0) - (bl.proceeds or 0)) > abs((na.cost_basis or 0) - bl.cost_basis):
            return "proceeds mismatch — possible fee allocation difference"
    if bl.cost_basis != (na.cost_basis or 0.0):
        return "cost basis mismatch — possibly a wash-sale adjustment net-alpha applied differently"
    return "small numerical drift"
