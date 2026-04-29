from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import text
from sqlmodel import Session

from net_alpha.db.repository import Repository
from net_alpha.engine.detector import detect_in_window
from net_alpha.engine.merge import merge_violations
from net_alpha.section_1256.classifier import classify_closed_trades
from net_alpha.section_1256.universe import universe_hash
from net_alpha.splits.apply import apply_manual_overrides, apply_splits


@dataclass
class MigrationRecomputeSummary:
    """Counts returned by migrate_existing_violations for user-facing banner."""

    reclassified_count: int  # Stale §1256 violations converted to ExemptMatch
    classifications_count: int  # §1256 classifications saved


def should_full_recompute(repo: Repository) -> bool:
    """True iff the §1256 universe hash in meta differs from the current bundled+user merge."""
    with Session(repo.engine) as session:
        row = session.exec(text("SELECT value FROM meta WHERE key='section_1256_universe_hash'")).first()
        stored = row[0] if row else None
    return stored != universe_hash()


def _stamp_universe_hash(repo: Repository) -> None:
    with Session(repo.engine) as session:
        session.exec(
            text(
                "INSERT INTO meta(key, value) VALUES ('section_1256_universe_hash', :v) "
                "ON CONFLICT(key) DO UPDATE SET value=:v"
            ).bindparams(v=universe_hash())
        )
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

        # Stamp universe hash so subsequent should_full_recompute() returns False.
        # Only stamp when a real recompute actually ran (data was present);
        # an empty DB must not suppress the trigger when trades are added later.
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


def migrate_existing_violations(repo: Repository) -> MigrationRecomputeSummary:
    """One-shot migration pass for DBs upgraded from v10 (pre-§1256 awareness).

    Steps:
    1. Backfill trades.is_section_1256=True for any §1256 trades whose flag
       was not set (can happen on DBs predating Task 8's add_import fix, where
       the column was added with DEFAULT 0 but not retroactively populated).
    2. Walk every WashSaleViolationRow; if either the loss or replacement trade
       is §1256, delete the violation and emit a corresponding ExemptMatch.
    3. Run the §1256 classifier over all closed §1256 trades and persist the
       classifications.
    4. Return a MigrationRecomputeSummary with counts for a user-facing banner.

    Idempotent: a second run finds no stale §1256 violations (they were already
    converted or never existed) and returns zero counts.
    """
    from sqlmodel import select as _select

    from net_alpha.db.tables import WashSaleViolationRow as _VRow
    from net_alpha.models.domain import ExemptMatch
    from net_alpha.section_1256.universe import is_section_1256 as _is_1256

    # ---- Step 1: Backfill is_section_1256 flag --------------------------------
    # Old DBs added the column with DEFAULT 0; trades that were §1256 contracts
    # (SPX, NDX, etc. options) may have the flag as False. Identify them by
    # consulting the universe function (YAML I/O) and update the DB column.
    all_trades = repo.all_trades()
    to_backfill = [t for t in all_trades if not t.is_section_1256 and _is_1256(t)]
    if to_backfill:
        repo.set_section_1256_flag([int(t.id) for t in to_backfill])
        # Reload so subsequent steps see the updated flag values.
        all_trades = repo.all_trades()

    # Build a trade-id → Trade index for fast lookup.
    trade_by_id: dict[str, object] = {t.id: t for t in all_trades}

    # ---- Step 2: Reclassify stale §1256 violations ---------------------------
    with Session(repo.engine) as session:
        violation_rows = session.exec(_select(_VRow)).all()

    stale_ids: list[int] = []
    new_exempt_matches: list[ExemptMatch] = []

    for row in violation_rows:
        loss = trade_by_id.get(str(row.loss_trade_id))
        buy = trade_by_id.get(str(row.replacement_trade_id))
        if loss is None or buy is None:
            # Orphaned violation — skip (don't reclassify, don't delete).
            continue
        if not (loss.is_section_1256 or buy.is_section_1256):
            # Plain equity wash sale — leave it alone.
            continue

        stale_ids.append(row.id)

        # Determine representative loss account display
        loss_account = getattr(loss, "account", "")
        buy_account = getattr(buy, "account", "")

        new_exempt_matches.append(
            ExemptMatch(
                loss_trade_id=str(row.loss_trade_id),
                triggering_buy_id=str(row.replacement_trade_id),
                exempt_reason="section_1256",
                rule_citation="IRC §1256(c)",
                notional_disallowed=row.disallowed_loss,
                confidence=row.confidence,
                matched_quantity=row.matched_quantity,
                loss_account=loss_account,
                buy_account=buy_account,
                loss_sale_date=loss.date,
                triggering_buy_date=buy.date,
                ticker=row.ticker or loss.ticker,
            )
        )

    repo.delete_violations_by_id(stale_ids)
    # NOTE: We do NOT call clear_exempt_matches() before save here. The migration
    # is one-shot (gated by section_1256_migration_done meta key); on second run,
    # new_exempts is empty because the stale violations were already removed.
    # If the meta key is manually reset and stale violations re-injected, duplicates
    # could result — accepted as outside the supported recovery path.
    if new_exempt_matches:
        repo.save_exempt_matches(new_exempt_matches)

    # ---- Step 3: Run §1256 classifier ----------------------------------------
    all_lots = repo.all_lots()
    classifications = classify_closed_trades(all_trades, all_lots)
    # NOTE: save_section_1256_classifications is upsert-by-trade_id, so re-running
    # on the same trade list overwrites cleanly — no clear needed.
    if classifications:
        repo.save_section_1256_classifications(classifications)

    return MigrationRecomputeSummary(
        reclassified_count=len(stale_ids),
        classifications_count=len(classifications),
    )
