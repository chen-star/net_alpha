"""Repository CRUD for splits + lot_overrides."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlmodel import SQLModel, create_engine

from net_alpha.db.repository import Repository
from net_alpha.models.domain import ImportRecord, Trade

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/splits_test.db")
    SQLModel.metadata.create_all(eng)
    return Repository(eng)


def _make_buy(account_display: str, ticker: str, day: date, qty: float = 10.0, cost: float = 1800.0) -> Trade:
    return Trade(account=account_display, date=day, ticker=ticker, action="Buy", quantity=qty, cost_basis=cost)


def _seed_import(repo: Repository, broker: str, label: str, trades: list[Trade]):
    account = repo.get_or_create_account(broker, label)
    record = ImportRecord(
        account_id=account.id,
        csv_filename="seed.csv",
        csv_sha256="sha-seed",
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


# ---------------------------------------------------------------------------
# Split tests
# ---------------------------------------------------------------------------


def test_add_and_list_splits(repo):
    sp_id = repo.add_split(
        symbol="AAPL",
        split_date=date(2020, 8, 31),
        ratio=4.0,
        source="yahoo",
    )
    assert sp_id > 0

    rows = repo.get_splits("AAPL")
    assert len(rows) == 1
    assert rows[0].symbol == "AAPL"
    assert rows[0].ratio == 4.0
    assert rows[0].source == "yahoo"


def test_add_split_idempotent_on_duplicate_key(repo):
    repo.add_split("AAPL", date(2020, 8, 31), 4.0, "yahoo")
    # Same (symbol, date) but different ratio: existing row wins, no exception.
    sp_id = repo.add_split("AAPL", date(2020, 8, 31), 5.0, "yahoo")
    assert sp_id is not None
    rows = repo.get_splits("AAPL")
    assert len(rows) == 1
    assert rows[0].ratio == 4.0  # unchanged


def test_get_splits_for_unknown_symbol_returns_empty(repo):
    assert repo.get_splits("NVDA") == []


# ---------------------------------------------------------------------------
# Lot override tests
# ---------------------------------------------------------------------------


def test_add_and_list_lot_overrides(repo, builders):
    a, _ = builders.seed_import(
        repo,
        "schwab",
        "lt",
        [
            builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5)),
        ],
    )
    trade = repo.get_trades_for_ticker("AAPL")[0]

    repo.add_lot_override(
        trade_id=int(trade.id),
        field="quantity",
        old_value=10.0,
        new_value=1.0,
        reason="split",
        split_id=None,
    )
    overrides = repo.get_lot_overrides_for_trade(int(trade.id))
    assert len(overrides) == 1
    assert overrides[0].field == "quantity"
    assert overrides[0].old_value == 10.0
    assert overrides[0].new_value == 1.0
