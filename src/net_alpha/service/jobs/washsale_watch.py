"""Job B — daily forward-looking wash-sale + §1091 watch over PositionTargets."""

from __future__ import annotations

import json
from datetime import date as _date

from net_alpha.engine import washsale_watch as ws_mod


def run_washsale_watch(*, repo, today: _date | None = None) -> dict:
    """Re-evaluate every PositionTarget; upsert results into washsale_watch_result."""
    today = today or _date.today()
    targets = repo.list_position_targets()
    risk_count = 0
    for t in targets:
        result = ws_mod.evaluate_target(target=t, repo=repo, today=today)
        repo.upsert_watch_result(
            target_id=t.id,
            status=result.status,
            severity=result.severity,
            reason=result.reason,
            triggering=json.dumps(result.triggering_trade_ids) if result.triggering_trade_ids else None,
            computed_at=today.isoformat(),
        )
        if result.status != "clean":
            risk_count += 1
    return {"targets": len(targets), "risk": risk_count}
