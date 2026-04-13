# tests/db/test_repository.py
import tempfile
from datetime import date
from pathlib import Path

import pytest
from sqlmodel import Session

from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import TradeRepository
from net_alpha.models.domain import OptionDetails, Trade


@pytest.fixture
def db_session():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        engine = get_engine(db_path)
        init_db(engine)
        with Session(engine) as session:
            yield session


def test_save_and_load_equity_trade(db_session):
    repo = TradeRepository(db_session)
    trade = Trade(
        account="Schwab",
        date=date(2024, 10, 15),
        ticker="TSLA",
        action="Sell",
        quantity=10.0,
        proceeds=2400.0,
        cost_basis=3600.0,
        raw_row_hash="abc123",
        schema_cache_id="sc1",
    )
    repo.save(trade)
    db_session.commit()

    loaded = repo.get_by_id(trade.id)
    assert loaded is not None
    assert loaded.ticker == "TSLA"
    assert loaded.proceeds == 2400.0
    assert loaded.is_loss() is True
    assert loaded.raw_row_hash == "abc123"


def test_save_and_load_option_trade(db_session):
    repo = TradeRepository(db_session)
    trade = Trade(
        account="Schwab",
        date=date(2024, 10, 15),
        ticker="TSLA",
        action="Buy",
        quantity=1.0,
        cost_basis=500.0,
        option_details=OptionDetails(
            strike=250.0, expiry=date(2024, 12, 20), call_put="C"
        ),
    )
    repo.save(trade)
    db_session.commit()

    loaded = repo.get_by_id(trade.id)
    assert loaded is not None
    assert loaded.is_option() is True
    assert loaded.option_details.strike == 250.0
    assert loaded.option_details.expiry == date(2024, 12, 20)
    assert loaded.option_details.call_put == "C"


def test_list_trades_by_account(db_session):
    repo = TradeRepository(db_session)
    repo.save(Trade(
        account="Schwab", date=date(2024, 1, 1), ticker="A", action="Buy", quantity=1.0
    ))
    repo.save(Trade(
        account="Robinhood", date=date(2024, 1, 1), ticker="B",
        action="Buy", quantity=1.0,
    ))
    repo.save(Trade(
        account="Schwab", date=date(2024, 1, 2), ticker="C", action="Buy", quantity=1.0
    ))
    db_session.commit()

    schwab = repo.list_by_account("Schwab")
    assert len(schwab) == 2


def test_list_all_trades(db_session):
    repo = TradeRepository(db_session)
    repo.save(Trade(
        account="Schwab", date=date(2024, 1, 1), ticker="A", action="Buy", quantity=1.0
    ))
    repo.save(Trade(
        account="Robinhood", date=date(2024, 1, 1), ticker="B",
        action="Buy", quantity=1.0,
    ))
    db_session.commit()

    all_trades = repo.list_all()
    assert len(all_trades) == 2


def test_find_by_hash(db_session):
    repo = TradeRepository(db_session)
    trade = Trade(
        account="Schwab", date=date(2024, 1, 1), ticker="A",
        action="Buy", quantity=1.0, raw_row_hash="hash123",
    )
    repo.save(trade)
    db_session.commit()

    found = repo.find_by_hash("hash123")
    assert found is not None
    assert found.id == trade.id

    assert repo.find_by_hash("nonexistent") is None


def test_find_by_semantic_key(db_session):
    repo = TradeRepository(db_session)
    trade = Trade(
        account="Schwab", date=date(2024, 1, 1), ticker="TSLA",
        action="Buy", quantity=10.0, proceeds=None,
    )
    repo.save(trade)
    db_session.commit()

    found = repo.find_by_semantic_key("Schwab", "2024-01-01", "TSLA", "Buy", 10.0, None)
    assert found is not None

    not_found = repo.find_by_semantic_key(
        "Schwab", "2024-01-01", "TSLA", "Buy", 99.0, None
    )
    assert not_found is None


def test_list_accounts(db_session):
    repo = TradeRepository(db_session)
    repo.save(Trade(
        account="Schwab", date=date(2024, 1, 1), ticker="A", action="Buy", quantity=1.0
    ))
    repo.save(Trade(
        account="Robinhood", date=date(2024, 1, 1), ticker="B",
        action="Buy", quantity=1.0,
    ))
    repo.save(Trade(
        account="Schwab", date=date(2024, 1, 2), ticker="C", action="Buy", quantity=1.0
    ))
    db_session.commit()

    accounts = repo.list_accounts()
    assert set(accounts) == {"Schwab", "Robinhood"}
