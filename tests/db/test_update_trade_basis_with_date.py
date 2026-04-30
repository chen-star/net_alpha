"""Tests for the trade_date extension to Repository.update_trade_basis."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from sqlmodel import SQLModel

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine
from net_alpha.db.repository import Repository
from net_alpha.models.domain import Trade


@pytest.fixture
def repo(tmp_path: Path) -> Repository:
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    SQLModel.metadata.create_all(engine)
    return Repository(engine)


def _make_transfer_in(repo: Repository, *, qty: float = 100.0, ticker: str = "AAPL") -> str:
    """Create one transfer_in trade (is_manual=False so it's treated as imported)."""
    repo.get_or_create_account("Schwab", "x")
    trade = Trade(
        account="Schwab/x",
        date=dt.date(2026, 2, 1),
        ticker=ticker,
        action="Buy",
        quantity=qty,
        basis_source="transfer_in",
    )
    saved = repo.create_manual_trade(trade, etf_pairs={})
    # create_manual_trade marks is_manual=True; flip it back so this row is
    # treated as an imported transfer (the path our form actually drives).
    repo._set_is_manual_for_test(int(saved.id), False)
    return str(saved.id)


def test_update_trade_basis_persists_optional_trade_date(repo: Repository) -> None:
    trade_id = _make_transfer_in(repo)
    repo.update_trade_basis(
        trade_id=trade_id,
        cost_basis=1500.00,
        basis_source="user_set",
        trade_date=dt.date(2024, 3, 12),
    )
    refreshed = repo.get_trade_by_id(int(trade_id))
    assert refreshed.cost_basis == 1500.00
    assert refreshed.basis_source == "user_set"
    assert refreshed.date == dt.date(2024, 3, 12)


def test_update_trade_basis_leaves_date_unchanged_when_none(repo: Repository) -> None:
    trade_id = _make_transfer_in(repo)
    repo.update_trade_basis(
        trade_id=trade_id,
        cost_basis=2000.00,
        basis_source="user_set",
        trade_date=None,
    )
    refreshed = repo.get_trade_by_id(int(trade_id))
    assert refreshed.cost_basis == 2000.00
    assert refreshed.date == dt.date(2026, 2, 1)  # original transfer date preserved
