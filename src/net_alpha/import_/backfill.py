"""One-time backfill of aggregate columns for legacy import rows.

Idempotent: only updates rows where aggregate columns are still NULL.
Called from db.connection.init_db immediately after migrate().
"""

from __future__ import annotations

from sqlmodel import Session, select

from net_alpha.db.repository import Repository
from net_alpha.db.tables import ImportRecordRow
from net_alpha.import_.aggregations import compute_import_aggregates


def backfill_import_aggregates(repo: Repository) -> int:
    """Recompute and persist aggregates for any import row missing them.

    Returns the number of rows updated.
    """
    with Session(repo.engine) as s:
        candidate_ids = [
            row.id for row in s.exec(select(ImportRecordRow).where(ImportRecordRow.min_trade_date.is_(None))).all()
        ]
    updated = 0
    for import_id in candidate_ids:
        trades = repo.trades_for_import(import_id)
        aggregates = compute_import_aggregates(trades=trades, parse_warnings=[])
        repo.update_import_aggregates(
            import_id=import_id,
            min_trade_date=aggregates.min_trade_date,
            max_trade_date=aggregates.max_trade_date,
            equity_count=aggregates.equity_count,
            option_count=aggregates.option_count,
            option_expiry_count=aggregates.option_expiry_count,
            parse_warnings=aggregates.parse_warnings,
        )
        updated += 1
    return updated
