# tests/db/test_repository.py
import tempfile
from datetime import date
from pathlib import Path

import pytest
from sqlmodel import Session

from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import (
    LotRepository,
    SchemaCacheRepository,
    TradeRepository,
    ViolationRepository,
)
from net_alpha.db.tables import SchemaCacheRow
from net_alpha.models.domain import Lot, OptionDetails, Trade, WashSaleViolation


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


def test_lot_save_and_list(db_session):
    repo = LotRepository(db_session)
    lot = Lot(
        trade_id="t1",
        account="Schwab",
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=10.0,
        cost_basis=2400.0,
        adjusted_basis=3600.0,
    )
    repo.save(lot)
    db_session.commit()

    lots = repo.list_all()
    assert len(lots) == 1
    assert lots[0].adjusted_basis == 3600.0


def test_violation_save_and_list(db_session):
    repo = ViolationRepository(db_session)
    v = WashSaleViolation(
        loss_trade_id="t1",
        replacement_trade_id="t2",
        confidence="Confirmed",
        disallowed_loss=1200.0,
        matched_quantity=10.0,
    )
    repo.save(v)
    db_session.commit()

    violations = repo.list_all()
    assert len(violations) == 1
    assert violations[0].confidence == "Confirmed"


def test_violation_delete_all(db_session):
    repo = ViolationRepository(db_session)
    repo.save(WashSaleViolation(
        loss_trade_id="t1", replacement_trade_id="t2",
        confidence="Confirmed", disallowed_loss=100.0, matched_quantity=1.0,
    ))
    repo.save(WashSaleViolation(
        loss_trade_id="t3", replacement_trade_id="t4",
        confidence="Probable", disallowed_loss=200.0, matched_quantity=2.0,
    ))
    db_session.commit()
    assert len(repo.list_all()) == 2

    repo.delete_all()
    db_session.commit()
    assert len(repo.list_all()) == 0


def test_schema_cache_save_and_find(db_session):
    repo = SchemaCacheRepository(db_session)
    row = SchemaCacheRow(
        id="sc1",
        broker_name="schwab",
        header_hash="sha256abc",
        column_mapping='{"date": "Date"}',
        option_format="schwab_human",
    )
    repo.save(row)
    db_session.commit()

    found = repo.find_by_broker_and_hash("schwab", "sha256abc")
    assert found is not None
    assert found.option_format == "schwab_human"

    assert repo.find_by_broker_and_hash("schwab", "other_hash") is None
