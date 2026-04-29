from __future__ import annotations

from datetime import timedelta

from sqlalchemy import text
from sqlmodel import Session

from net_alpha.db.repository import Repository
from net_alpha.engine.detector import detect_in_window
from net_alpha.engine.merge import merge_violations
from net_alpha.section_1256.classifier import classify_closed_trades
from net_alpha.section_1256.universe import universe_hash
from net_alpha.splits.apply import apply_manual_overrides, apply_splits


def should_full_recompute(repo: Repository) -> bool:
    """True iff the §1256 universe hash in meta differs from the current bundled+user merge."""
    with Session(repo.engine) as session:
        row = session.exec(text(
            "SELECT value FROM meta WHERE key='section_1256_universe_hash'"
        )).first()
        stored = row[0] if row else None
    return stored != universe_hash()


def _stamp_universe_hash(repo: Repository) -> None:
    with Session(repo.engine) as session:
        session.exec(text(
            "INSERT INTO meta(key, value) VALUES ('section_1256_universe_hash', :v) "
            "ON CONFLICT(key) DO UPDATE SET value=:v"
        ).bindparams(v=universe_hash()))
        session.commit()


def recompute_all(repo: Repository) -> None:
    """Recompute all wash-sale violations, persist exempt matches, run §1256
    classifier, and stamp the universe hash.

    Loads ETF pairs from the default bundled + user YAML paths so callers
    don't need to supply them.
    """
    from net_alpha.engine.etf_pairs import load_etf_pairs

    etf_pairs = load_etf_pairs()
    recompute_all_violations(repo, etf_pairs)

    # Persist exempt matches from the last full detection pass.
    # Re-run detect to get the full DetectionResult including exempt_matches.
    all_trades = repo.all_trades()
    accounts = repo.list_accounts()
    gl_by_account = {a.id: repo.get_gl_lots_for_account(a.id) for a in accounts}

    all_dates: list = [t.date for t in all_trades]
    for lots in gl_by_account.values():
        all_dates.extend(lot.closed_date for lot in lots)

    if all_dates:
        win_start = min(all_dates) - timedelta(days=30)
        win_end = max(all_dates) + timedelta(days=30)
        det = detect_in_window(
            repo.trades_in_window(win_start, win_end),
            win_start,
            win_end,
            etf_pairs=etf_pairs,
        )

        # Persist exempt matches
        repo.clear_exempt_matches()
        repo.save_exempt_matches(det.exempt_matches)

        # Run §1256 classifier and persist classifications
        all_lots = repo.all_lots()
        classifications = classify_closed_trades(all_trades, all_lots)
        repo.clear_section_1256_classifications()
        repo.save_section_1256_classifications(classifications)

    # Stamp universe hash so subsequent should_full_recompute() returns False
    _stamp_universe_hash(repo)


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
