"""Verify Repository.tickers_with_open_lots() returns the set of tickers
that have at least one lot row with quantity > 0. Used by the palette
to rank held tickers ahead of targeted-only or merely-traded tickers.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine

from net_alpha.db.repository import Repository
from net_alpha.db.tables import LotRow


@pytest.fixture
def repo(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/v2.db")
    SQLModel.metadata.create_all(eng)
    return Repository(eng)


def _seed_lot(engine, *, ticker: str, quantity: float) -> None:
    """Seed one LotRow. trade_id and account_id are placeholder integers — the
    helper under test does not join through them."""
    with Session(engine) as s:
        s.add(
            LotRow(
                trade_id=1,
                account_id=1,
                ticker=ticker,
                trade_date="2025-01-01",
                quantity=quantity,
                cost_basis=100.0,
                adjusted_basis=100.0,
            )
        )
        s.commit()


def test_returns_tickers_with_positive_quantity(repo):
    _seed_lot(repo.engine, ticker="AAPL", quantity=10.0)
    _seed_lot(repo.engine, ticker="NVDA", quantity=5.0)
    _seed_lot(repo.engine, ticker="OLD", quantity=0.0)

    result = repo.tickers_with_open_lots()
    assert result == {"AAPL", "NVDA"}


def test_empty_db_returns_empty_set(repo):
    assert repo.tickers_with_open_lots() == set()
