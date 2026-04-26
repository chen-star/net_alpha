from datetime import date, datetime
from pathlib import Path

from sqlmodel import SQLModel

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine
from net_alpha.db.repository import Repository
from net_alpha.import_.backfill import backfill_import_aggregates
from net_alpha.models.domain import ImportRecord, Trade


def _settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path)


def _make_repo(tmp_path: Path) -> Repository:
    eng = get_engine(_settings(tmp_path).db_path)
    SQLModel.metadata.create_all(eng)
    return Repository(eng)


def _trade(account, day, ticker="AAPL"):
    return Trade(
        account=account,
        date=day,
        ticker=ticker,
        action="Buy",
        quantity=10.0,
        proceeds=None,
        cost_basis=1000.0,
    )


def test_backfill_fills_missing_aggregates(tmp_path: Path):
    repo = _make_repo(tmp_path)
    acct = repo.get_or_create_account("schwab", "tax")
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="legacy.csv",
        csv_sha256="x",
        imported_at=datetime(2026, 1, 1),
        trade_count=2,
        # Aggregate fields intentionally omitted to simulate a legacy v3 row.
    )
    trades = [_trade(acct.display(), date(2026, 1, 5)), _trade(acct.display(), date(2026, 1, 10))]
    repo.add_import(acct, rec, trades)

    # Confirm aggregates start empty for this row.
    summary_before = repo.list_imports()[0]
    assert summary_before.min_trade_date is None

    n = backfill_import_aggregates(repo)
    assert n == 1

    summary = repo.list_imports()[0]
    assert summary.min_trade_date == date(2026, 1, 5)
    assert summary.max_trade_date == date(2026, 1, 10)
    assert summary.equity_count == 2
    assert summary.option_count == 0


def test_backfill_is_idempotent(tmp_path: Path):
    repo = _make_repo(tmp_path)
    acct = repo.get_or_create_account("schwab", "tax")
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="legacy.csv",
        csv_sha256="x",
        imported_at=datetime(2026, 1, 1),
        trade_count=1,
    )
    repo.add_import(acct, rec, [_trade(acct.display(), date(2026, 1, 5))])

    assert backfill_import_aggregates(repo) == 1
    assert backfill_import_aggregates(repo) == 0
