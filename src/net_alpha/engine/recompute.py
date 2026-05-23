from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from loguru import logger
from sqlalchemy import text
from sqlmodel import Session, select

from net_alpha.db.migrations import CURRENT_SCHEMA_VERSION
from net_alpha.db.repository import Repository
from net_alpha.db.tables import AccountRow
from net_alpha.engine.detector import detect_in_window
from net_alpha.engine.merge import merge_violations
from net_alpha.models.accounts import AccountType
from net_alpha.section_1256.classifier import classify_closed_trades
from net_alpha.section_1256.mtm import mark_to_market
from net_alpha.section_1256.universe import load_universe, universe_hash
from net_alpha.splits.apply import apply_manual_overrides, apply_splits


def _warn_unmapped_account_types(repo: Repository) -> None:
    """Audit #13: emit a single warning per recompute listing every account
    whose ``type`` column holds an unrecognized string. These rows silently
    default to TAXABLE downstream, but the user should classify them so the
    wash-sale engine and the carryforward agree on what to tax.
    """
    valid = {t.value for t in AccountType}
    unmapped: list[str] = []
    with Session(repo.engine) as s:
        rows = s.exec(select(AccountRow.broker, AccountRow.label, AccountRow.type)).all()
        for broker, label, type_str in rows:
            if not type_str or type_str not in valid:
                unmapped.append(f"{broker}/{label}")
    if unmapped:
        logger.warning(
            "Unmapped account types defaulted to TAXABLE; please classify: {}",
            ", ".join(sorted(unmapped)),
        )


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


def _fmv_fn_for_recompute(repo: Repository):
    """Production FMV fn — builds a cached PriceProvider from the repo's engine; monkeypatchable in tests."""
    from net_alpha.config import Settings, load_pricing_config
    from net_alpha.pricing.cache import PriceCache
    from net_alpha.pricing.service import PricingService
    from net_alpha.pricing.yahoo import YahooPriceProvider
    from net_alpha.pricing.year_end import year_end_fmv

    pcfg = load_pricing_config(Settings().config_yaml_path)
    cache = PriceCache(repo.engine, ttl_seconds=pcfg.cache_ttl_seconds)
    provider = PricingService(provider=YahooPriceProvider(), cache=cache, enabled=pcfg.enable_remote)

    def fn(ticker, option_details, year):
        return year_end_fmv(ticker=ticker, option_details=option_details, year=year, provider=provider)

    return fn


def _run_section_1256_pass(repo: Repository, all_trades, all_lots) -> None:
    """Run §1256 classifier, write per-year MTM rows, then re-classify with prior-year basis carry."""
    # First pass: classifier with cost basis (MTM rows from prior runs were
    # cleared below). Persist so any downstream readers between passes see a
    # consistent state.
    classifications = classify_closed_trades(all_trades, all_lots)
    repo.clear_section_1256_classifications()
    repo.save_section_1256_classifications(classifications)

    # MTM pass: scan every year from the earliest §1256 trade through the current
    # year.  mark_to_market returns [] for years with no open positions, so
    # iterating over "gap" years is a cheap no-op.  The old gap-stop probe broke
    # the §1256(a)(2) basis-carry chain when multiple positions existed with a
    # year-long gap between them (e.g. position A closed 2022-01-15, position B
    # opened 2024-03-01 — the probe stopped at 2023 and never wrote A's 2020/2021
    # MTM rows, leaving B's 2022 sell with a broken prior-year basis chain).
    universe = load_universe()
    current_year = date.today().year

    # Determine the earliest tax year to mark — bounded by the oldest §1256 trade
    # in the ledger.
    earliest_trade_year: int | None = None
    for t in all_trades:
        if not (t.is_section_1256 and t.option_details is not None):
            continue
        y = t.date.year
        if earliest_trade_year is None or y < earliest_trade_year:
            earliest_trade_year = y

    repo.clear_section_1256_mtm()
    if earliest_trade_year is not None:
        # Cap lookback at 30 years for safety against pathologically old data.
        start_year = max(earliest_trade_year, current_year - 30)
        fmv_fn = _fmv_fn_for_recompute(repo)
        for tax_year in range(start_year, current_year + 1):
            rows = mark_to_market(
                trades=all_trades,
                lots=all_lots,
                universe=universe,
                tax_year=tax_year,
                fmv_fn=fmv_fn,
                prior_year_mtm_basis_fn=repo.prior_year_mtm_basis_for_position,
            )
            if rows:
                repo.save_section_1256_mtm(rows)

    # Re-run classifier honoring prior-year MTM basis per §1256(a)(2).
    classifications = classify_closed_trades(
        all_trades,
        all_lots,
        prior_year_mtm_basis_fn=repo.prior_year_mtm_basis_for_position,
    )
    repo.clear_section_1256_classifications()
    repo.save_section_1256_classifications(classifications)


def recompute_all(repo: Repository) -> None:
    """Convenience wrapper: load ETF pairs and call recompute_all_violations.

    Recomputes violations, persists exempt matches, runs the §1256 classifier,
    and stamps the universe hash + engine version. Callers that already hold
    the ETF pairs dict should call recompute_all_violations directly.
    """
    from net_alpha.engine.etf_pairs import load_etf_pairs

    etf_pairs = load_etf_pairs()
    recompute_all_violations(repo, etf_pairs)


def _rebuild_adjusted_basis_from_violations(repo: Repository) -> None:
    """Reset every lot's adjusted_basis to its cost_basis plus the sum of
    every currently-persisted deferred wash-sale violation whose
    replacement_trade_id points at that lot's trade.

    Idempotent. Run after replace_violations_in_window + replace_lots_in_window
    so the lot state matches the violation state.

    Only ``kind="deferred"`` violations bump basis. The other two kinds are
    intentionally excluded:

    - ``kind="permanent_ira"`` — Rev. Rul. 2008-5: §1091(a) disallows the loss
      but §1091(d)'s basis rollover can't apply (no basis ledger in a
      tax-advantaged account). Loss is permanently lost; no lot to mutate.

    - ``kind="deferred_to_contract"`` — sold-put trigger. §1091(d) rolls basis
      into "the contract to acquire," but v1 doesn't track basis on STO
      contracts. Out of scope; user tracks manually until close/assignment.

    Manual lot_overrides are applied AFTER this pass and take final precedence,
    so user-edited basis remains intact.
    """
    from collections import defaultdict

    all_lots = repo.all_lots()
    all_violations = repo.all_violations()

    bumps_by_trade_id: dict[str, float] = defaultdict(float)
    for v in all_violations:
        if v.kind != "deferred":
            continue
        bumps_by_trade_id[str(v.replacement_trade_id)] += float(v.disallowed_loss)

    for lot in all_lots:
        expected = float(lot.cost_basis) + bumps_by_trade_id.get(str(lot.trade_id), 0.0)
        # Comparison floor at $0.005 — sub-cent FP wobble is not worth a UPDATE.
        if abs(float(lot.adjusted_basis) - expected) > 0.005:
            repo.update_lot_qty_and_basis(int(lot.id), quantity=float(lot.quantity), adjusted_basis=expected)


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
    _warn_unmapped_account_types(repo)

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
        account_types=repo.account_types_by_display(),
    )
    merged = merge_violations(
        engine_violations=det.violations,
        gl_lots_by_account=gl_by_account,
    )
    repo.replace_violations_in_window(win_start, win_end, merged)
    repo.replace_lots_in_window(win_start, win_end, det.lots)

    # Rebuild adjusted_basis on every lot from cost_basis + sum of surviving
    # deferred-violation bumps. The detector provisionally bumps each
    # replacement lot's basis the instant it identifies a wash-sale
    # candidate, but merge_violations may drop the engine's violation when
    # Schwab's Realized G/L disagrees (rule 2a: wash_sale=False). Without
    # this pass the bump survives in det.lots and accumulates as stale
    # residue across recompute cycles — the source of phantom BasisRecon
    # findings against open lots that have no live violation.
    _rebuild_adjusted_basis_from_violations(repo)

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

    # Run §1256 classifier + MTM pass + re-classify with prior-year basis carry.
    # Reload lots AFTER splits/overrides have been applied so adjusted_basis is correct.
    all_lots = repo.all_lots()
    _run_section_1256_pass(repo, all_trades, all_lots)

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

    # ---- Step 3: Run §1256 classifier + MTM pass -----------------------------
    all_lots = repo.all_lots()
    _run_section_1256_pass(repo, all_trades, all_lots)
    # Re-read classifications to report the count (the pass clears + rewrites).
    classifications = repo.list_section_1256_classifications()

    return MigrationRecomputeSummary(
        reclassified_count=len(stale_ids),
        classifications_count=len(classifications),
    )
