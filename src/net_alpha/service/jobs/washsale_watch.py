"""Job B — daily forward-looking wash-sale + §1091 watch over PositionTargets.

The engine in ``net_alpha.engine.washsale_watch`` expects a per-account target
shape (``.broker``, ``.account``, ``.target_shares``/``.target_dollars``,
``.id``), but the production schema stores targets per-symbol-only
(``position_targets`` has no broker/account columns). This job bridges the
two: for every target row we evaluate the (target, account) pair against
every known account and keep the worst-severity result as the single
upserted row per target_id. That matches the ``washsale_watch_result``
schema, which uniques on ``target_id``.
"""

from __future__ import annotations

import json
from datetime import date as _date
from types import SimpleNamespace

from net_alpha.engine import washsale_watch as ws_mod
from net_alpha.targets.models import TargetUnit

_SEVERITY_ORDER = {"none": 0, "soft": 1, "hard": 2}


def _wrap(*, row, account) -> SimpleNamespace:
    """Build the per-account target wrapper the engine expects."""
    unit = row.target_unit if isinstance(row.target_unit, str) else row.target_unit.value
    target_shares = row.target_amount if unit == TargetUnit.SHARES.value else None
    target_dollars = row.target_amount if unit == TargetUnit.USD.value else None
    return SimpleNamespace(
        id=row.id,
        symbol=row.symbol,
        broker=account.broker,
        account=account.label,
        target_shares=target_shares,
        target_dollars=target_dollars,
    )


def run_washsale_watch(*, repo, today: _date | None = None) -> dict:
    """Re-evaluate every PositionTarget; upsert results into washsale_watch_result."""
    today = today or _date.today()
    # Use the row variant so we keep the integer `id` for the result upsert —
    # the public list_targets() drops it.
    target_rows = list(repo.list_target_rows())
    accounts = list(repo.list_accounts())
    risk_count = 0
    for row in target_rows:
        # Worst severity across (target, account) pairs becomes the per-target
        # result. Fallback to a clean result when no accounts exist yet.
        best = ws_mod.WatchResult(status="clean", severity="none")
        for acct in accounts:
            wrapped = _wrap(row=row, account=acct)
            r = ws_mod.evaluate_target(target=wrapped, repo=repo, today=today)
            if _SEVERITY_ORDER.get(r.severity, 0) > _SEVERITY_ORDER.get(best.severity, 0):
                best = r
            elif best.status == "clean" and r.status != "clean":
                best = r  # surface first non-clean status when severities tie at 'none'
        repo.upsert_watch_result(
            target_id=row.id,
            status=best.status,
            severity=best.severity,
            reason=best.reason,
            triggering=json.dumps(best.triggering_trade_ids) if best.triggering_trade_ids else None,
            computed_at=today.isoformat(),
        )
        if best.status != "clean":
            risk_count += 1
    return {"targets": len(target_rows), "risk": risk_count}
