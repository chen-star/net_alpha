from __future__ import annotations

from datetime import datetime

import pytest

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.domain import CashEvent, ImportRecord, Trade


@pytest.fixture
def repo(tmp_path) -> Repository:
    """A clean Repository backed by a tmp_path SQLite DB."""
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    return Repository(engine)


@pytest.fixture
def schwab_account(repo: Repository):
    """A pre-created Schwab account row for tests that need an account_id."""
    return repo.get_or_create_account(broker="Schwab", label="Tax")


def seed_import(
    repo: Repository,
    account,
    trades: list[Trade],
    *,
    filename: str = "t.csv",
    cash_events: list[CashEvent] | None = None,
) -> None:
    """Helper: create an ImportRecord and call repo.add_import.

    Args:
        repo: Repository instance to add import to.
        account: Account (from fixture or get_or_create_account).
        trades: List of Trade objects to import.
        filename: CSV filename for the ImportRecord (default "t.csv").
        cash_events: Optional list of CashEvent objects (default None).
    """
    record = ImportRecord(
        account_id=account.id,
        csv_filename=filename,
        csv_sha256=f"sha-{filename}",
        imported_at=datetime.now(),
        trade_count=len(trades),
    )
    repo.add_import(account, record, trades, cash_events=cash_events)
