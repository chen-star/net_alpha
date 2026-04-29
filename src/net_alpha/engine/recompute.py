from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import text
from sqlmodel import Session

from net_alpha.db.migrations import CURRENT_SCHEMA_VERSION
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
    """True iff the §1256 universe hash OR the wash-sale engine version in meta
    differs from the current bundled universe / CURRENT_SCHEMA_VERSION.
    """
    with Session(repo.engine) as session:
        hash_row = session.exec(text("SELECT value FROM meta WHERE key='section_1256_universe_hash'")).first()
        version_row = session.exec(text("SELECT value FROM meta WHERE key='wash_sale_engine_version'")).first()
        stored_hash = hash_row[0] if hash_row else None
        stored_version = version_row[0] if version_row else None
    return (stored_hash != universe_hash()) or (stored_version != str(CURRENT_SCHEMA_VERSION))


def _stamp_universe_hash(repo: Repository) -> None:
    """Stamp universe hash AND engine version in meta."""
    with Session(repo.engine) as session:
        session.exec(
            text(
                "INSERT INTO meta(key, value) VALUES ('section_1256_universe_hash', :v) "
                "ON CONFLICT(key) DO UPDATE SET value=:v"
            ).bindparams(v=universe_hash())
        )
        session.exec(
            text(
                "INSERT INTO meta(key, value) VALUES ('wash_sale_engine_version', :v) "
                "ON CONFLICT(key) DO UPDATE SET value=:v"
            ).bindparams(v=str(CURRENT_SCHEMA_VERSION))
        )
        session.commit()


def recompute_all(repo: Repository) -> None:
    """Convenience wrapper: load ETF pairs and call recompute_all_violations.

    Recomputes violations, persists exempt matches, runs the §1256 classifier,
    and stamps the universe hash + engine version. Callers that already hold
    the ETF pairs dict should call recompute_all_violations directly.
    """
    from net_alpha.engine.etf_pairs import load_etf_pairs

    etf_pairs = load_etf_pairs()
    recompute_all_violations(repo, etf_pairs)


def recompute_all_violations(repo: Repository, etf_pairs: dict[str, list[str]]) -> None:
    """Recompute all wash-sale violations from scratch across all accounts.

    Schwab G/L data can downgrade or suppress engine-detected violations whose
    loss_sale_date sits outside the immediate ±30-day window of any single
    upload, so per-import incremental recompute leaves stale Confirmed/Probable
    labels behind. Run this after every upload or delete to keep state coherent.

    Also persists exempt matches (§1256 trades that were skipped by the wash-sale
    detector) and runs the §1256 60/40 classifier over all closed §1256 trades.
    Stamps the universe hash and engine version in meta so should_full_recompute()
    returns False until the universe or engine changes again.
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

    # C2: Persist exempt matches from this recompute pass.
    # clear_exempt_matches() is a full table wipe — acceptable for v1 where we
    # always recompute globally (no windowed exempt-match persistence).
    repo.clear_exempt_matches()
    repo.save_exempt_matches(det.exempt_matches)

    # C2: Run §1256 classifier over all closed §1256 trades and persist classifications.
    # Reload lots AFTER splits/overrides have been applied so adjusted_basis is correct.
    all_lots = repo.all_lots()
    classifications = classify_closed_trades(all_trades, all_lots)
    repo.clear_section_1256_classifications()
    repo.save_section_1256_classifications(classifications)

    # Stamp universe hash + engine version so should_full_recompute() returns False
    # until the universe YAML changes or the binary is upgraded.
    _stamp_universe_hash(repo)


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
