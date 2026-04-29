"""Existing wash-sale violations on §1256 contracts should be reclassified
as ExemptMatch records on first launch after upgrade."""

from datetime import date, datetime
from decimal import Decimal

from sqlmodel import Session, SQLModel, create_engine

import net_alpha.db.tables  # noqa: F401
from net_alpha.db.migrations import migrate
from net_alpha.db.repository import Repository
from net_alpha.db.tables import WashSaleViolationRow
from net_alpha.engine.recompute import migrate_existing_violations
from net_alpha.models.domain import ImportRecord, OptionDetails, Trade


def _make_repo(tmp_path, db_name="legacy.db"):
    engine = create_engine(f"sqlite:///{tmp_path}/{db_name}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        migrate(session)
    return Repository(engine)


def _seed_spx_trades(repo: Repository) -> tuple[int, int]:
    """Plant two SPX option trades (loss + buy) and return their DB int IDs."""
    acct = repo.get_or_create_account("test", "personal")
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="spx.csv",
        csv_sha256="h_spx",
        imported_at=datetime(2024, 10, 1),
        trade_count=0,
    )
    trades = [
        Trade(
            date=date(2024, 9, 15),
            account=acct.display(),
            ticker="SPX",
            action="Sell",
            quantity=1,
            proceeds=Decimal("100"),
            cost_basis=Decimal("721.50"),
            option_details=OptionDetails(strike=4500, expiry=date(2025, 12, 19), call_put="C"),
            is_section_1256=True,
        ),
        Trade(
            date=date(2024, 9, 22),
            account=acct.display(),
            ticker="SPX",
            action="Buy",
            quantity=1,
            proceeds=Decimal("100"),
            cost_basis=Decimal("100"),
            option_details=OptionDetails(strike=4500, expiry=date(2025, 12, 19), call_put="C"),
            is_section_1256=True,
        ),
    ]
    repo.add_import(acct, rec, trades)

    saved = repo.all_trades()
    assert len(saved) == 2, f"Expected 2 trades, got {len(saved)}"
    sell = next(t for t in saved if t.action == "Sell")
    buy = next(t for t in saved if t.action == "Buy")
    return int(sell.id), int(buy.id)


def _inject_stale_violation(repo: Repository, sell_id: int, buy_id: int) -> None:
    """Insert a stale WashSaleViolationRow directly using int PKs."""
    acct = repo.list_accounts()[0]
    with Session(repo.engine) as session:
        session.add(
            WashSaleViolationRow(
                loss_trade_id=sell_id,
                replacement_trade_id=buy_id,
                loss_account_id=acct.id,
                buy_account_id=acct.id,
                loss_sale_date="2024-09-15",
                triggering_buy_date="2024-09-22",
                ticker="SPX",
                confidence="Confirmed",
                disallowed_loss=621.50,
                matched_quantity=1.0,
                source="engine",
            )
        )
        session.commit()


def _legacy_db_with_stale_spx_violation(tmp_path):
    repo = _make_repo(tmp_path)
    sell_id, buy_id = _seed_spx_trades(repo)
    _inject_stale_violation(repo, sell_id, buy_id)
    return repo


def test_migration_recompute_reclassifies_stale_spx_violation(tmp_path):
    repo = _legacy_db_with_stale_spx_violation(tmp_path)
    assert len(repo.all_violations()) == 1

    summary = migrate_existing_violations(repo)

    assert len(repo.all_violations()) == 0
    assert len(repo.list_exempt_matches()) == 1
    assert summary.reclassified_count == 1


def test_migration_recompute_summary_includes_counts(tmp_path):
    repo = _legacy_db_with_stale_spx_violation(tmp_path)
    summary = migrate_existing_violations(repo)
    assert hasattr(summary, "reclassified_count")
    assert hasattr(summary, "classifications_count")


def test_migration_recompute_no_op_when_no_1256_violations(tmp_path):
    """A DB with only non-§1256 violations should leave violations intact."""
    repo = _make_repo(tmp_path)
    acct = repo.get_or_create_account("test", "personal")
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="aapl.csv",
        csv_sha256="h_aapl",
        imported_at=datetime(2024, 10, 1),
        trade_count=0,
    )
    # Plain equity trades — not §1256
    trades = [
        Trade(
            date=date(2024, 9, 15),
            account=acct.display(),
            ticker="AAPL",
            action="Sell",
            quantity=10,
            proceeds=Decimal("1500"),
            cost_basis=Decimal("2000"),
            is_section_1256=False,
        ),
        Trade(
            date=date(2024, 9, 22),
            account=acct.display(),
            ticker="AAPL",
            action="Buy",
            quantity=10,
            proceeds=Decimal("1600"),
            cost_basis=Decimal("1600"),
            is_section_1256=False,
        ),
    ]
    repo.add_import(acct, rec, trades)
    saved = repo.all_trades()
    sell_id = int(next(t for t in saved if t.action == "Sell").id)
    buy_id = int(next(t for t in saved if t.action == "Buy").id)

    # Inject an equity (non-§1256) wash sale violation
    with Session(repo.engine) as session:
        session.add(
            WashSaleViolationRow(
                loss_trade_id=sell_id,
                replacement_trade_id=buy_id,
                loss_account_id=acct.id,
                buy_account_id=acct.id,
                loss_sale_date="2024-09-15",
                triggering_buy_date="2024-09-22",
                ticker="AAPL",
                confidence="Confirmed",
                disallowed_loss=500.0,
                matched_quantity=10.0,
                source="engine",
            )
        )
        session.commit()

    assert len(repo.all_violations()) == 1

    summary = migrate_existing_violations(repo)

    # Equity violation must NOT be touched
    assert len(repo.all_violations()) == 1
    assert len(repo.list_exempt_matches()) == 0
    assert summary.reclassified_count == 0


def test_migration_recompute_backfills_is_section_1256_flag(tmp_path):
    """If trades have is_section_1256=False in the DB (old DB before flag was populated),
    the migration pass should backfill the flag and still reclassify the violation."""
    repo = _make_repo(tmp_path)
    acct = repo.get_or_create_account("test", "personal")
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="spx2.csv",
        csv_sha256="h_spx2",
        imported_at=datetime(2024, 10, 1),
        trade_count=0,
    )
    # Import WITHOUT is_section_1256 flag set (simulates old DB data)
    trades = [
        Trade(
            date=date(2024, 9, 15),
            account=acct.display(),
            ticker="SPX",
            action="Sell",
            quantity=1,
            proceeds=Decimal("100"),
            cost_basis=Decimal("721.50"),
            option_details=OptionDetails(strike=4500, expiry=date(2025, 12, 19), call_put="C"),
            is_section_1256=False,  # Deliberately not set
        ),
        Trade(
            date=date(2024, 9, 22),
            account=acct.display(),
            ticker="SPX",
            action="Buy",
            quantity=1,
            proceeds=Decimal("100"),
            cost_basis=Decimal("100"),
            option_details=OptionDetails(strike=4500, expiry=date(2025, 12, 19), call_put="C"),
            is_section_1256=False,  # Deliberately not set
        ),
    ]
    repo.add_import(acct, rec, trades)

    saved = repo.all_trades()
    sell_id = int(next(t for t in saved if t.action == "Sell").id)
    buy_id = int(next(t for t in saved if t.action == "Buy").id)

    _inject_stale_violation(repo, sell_id, buy_id)
    assert len(repo.all_violations()) == 1

    summary = migrate_existing_violations(repo)

    # Violation should be reclassified even though flag started as False
    assert len(repo.all_violations()) == 0
    assert len(repo.list_exempt_matches()) == 1
    assert summary.reclassified_count == 1


def test_migration_recompute_idempotent(tmp_path):
    """Running migrate_existing_violations twice must not double-create exempt matches."""
    repo = _legacy_db_with_stale_spx_violation(tmp_path)

    summary1 = migrate_existing_violations(repo)
    summary2 = migrate_existing_violations(repo)

    assert summary1.reclassified_count == 1
    assert summary2.reclassified_count == 0  # Nothing left to reclassify
    assert len(repo.list_exempt_matches()) == 1


def test_migration_recompute_runs_section_1256_classifier(tmp_path):
    """After migration, §1256 classifications should be saved for closed SPX trades."""
    repo = _legacy_db_with_stale_spx_violation(tmp_path)
    # Clear any classifications that might exist
    repo.clear_section_1256_classifications()

    summary = migrate_existing_violations(repo)

    # The classifier should produce at least one classification (for the Sell)
    classifications = repo.list_section_1256_classifications()
    assert len(classifications) >= 1
    assert summary.classifications_count >= 1
