from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from sqlmodel import SQLModel, create_engine

from net_alpha.db.repository import Repository
from net_alpha.models.domain import Account, ImportRecord, Trade


@pytest.fixture
def repo(tmp_path: Path):
    eng = create_engine(f"sqlite:///{tmp_path}/pricing_test.db")
    SQLModel.metadata.create_all(eng)
    return Repository(eng)


def _make_buy(
    account_display: str,
    ticker: str,
    day: date,
    qty: float = 10.0,
    cost: float = 1800.0,
) -> Trade:
    return Trade(
        account=account_display,
        date=day,
        ticker=ticker,
        action="Buy",
        quantity=qty,
        proceeds=None,
        cost_basis=cost,
    )


def _seed_import(
    repo: Repository,
    broker: str,
    label: str,
    trades: list[Trade],
    csv_filename: str = "seed.csv",
) -> tuple[Account, int]:
    account = repo.get_or_create_account(broker, label)
    record = ImportRecord(
        account_id=account.id,
        csv_filename=csv_filename,
        csv_sha256=f"sha-{csv_filename}",
        imported_at=datetime.now(),
        trade_count=len(trades),
    )
    result = repo.add_import(account, record, trades)
    return account, result.import_id


@pytest.fixture
def builders():
    """Expose builder functions to tests via a single fixture."""
    return type(
        "B",
        (),
        {
            "make_buy": staticmethod(_make_buy),
            "seed_import": staticmethod(_seed_import),
        },
    )
