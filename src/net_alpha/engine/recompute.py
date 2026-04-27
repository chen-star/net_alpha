from __future__ import annotations

from datetime import timedelta

from net_alpha.db.repository import Repository
from net_alpha.engine.detector import detect_in_window
from net_alpha.engine.merge import merge_violations
from net_alpha.splits.apply import apply_manual_overrides, apply_splits


def recompute_all_violations(repo: Repository, etf_pairs: dict[str, list[str]]) -> None:
    """Recompute all wash-sale violations from scratch across all accounts.

    Schwab G/L data can downgrade or suppress engine-detected violations whose
    loss_sale_date sits outside the immediate ±30-day window of any single
    upload, so per-import incremental recompute leaves stale Confirmed/Probable
    labels behind. Run this after every upload or delete to keep state coherent.
    """
    all_trades = repo.all_trades()
    accounts = repo.list_accounts()
    gl_by_account = {a.id: repo.get_gl_lots_for_account(a.id) for a in accounts}

    all_dates: list = [t.date for t in all_trades]
    for lots in gl_by_account.values():
        all_dates.extend(lot.closed_date for lot in lots)

    if not all_dates:
        return

    win_start = min(all_dates) - timedelta(days=30)
    win_end = max(all_dates) + timedelta(days=30)

    det = detect_in_window(
        repo.trades_in_window(win_start, win_end),
        win_start,
        win_end,
        etf_pairs=etf_pairs,
    )
    merged = merge_violations(
        engine_violations=det.violations,
        gl_lots_by_account=gl_by_account,
    )
    repo.replace_violations_in_window(win_start, win_end, merged)
    repo.replace_lots_in_window(win_start, win_end, det.lots)

    # Re-apply known splits, then manual overrides, to the freshly-regenerated lots.
    # Order matters: splits establish the split-adjusted baseline; manual overrides
    # layer on top and take final precedence.
    apply_splits(repo)
    apply_manual_overrides(repo)
