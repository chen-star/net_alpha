from datetime import date, datetime

import pytest
from sqlmodel import SQLModel

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine
from net_alpha.db.repository import Repository
from net_alpha.models.domain import ImportRecord, Trade


@pytest.fixture
def repo(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    SQLModel.metadata.create_all(engine)
    return Repository(engine)


def _make_trade(account_display: str, ticker: str, day: date, action: str = "Buy",
                qty: float = 10.0, cost: float = 1800.0, proceeds: float | None = None) -> Trade:
    return Trade(
        account=account_display,
        date=day,
        ticker=ticker,
        action=action,
        quantity=qty,
        proceeds=proceeds,
        cost_basis=cost,
    )


def _seed(repo: Repository, broker: str, label: str, trades: list[Trade]):
    account = repo.get_or_create_account(broker, label)
    record = ImportRecord(
        account_id=account.id,
        csv_filename="x.csv",
        csv_sha256="sha",
        imported_at=datetime.now(),
        trade_count=len(trades),
    )
    repo.add_import(account, record, trades)


def test_list_distinct_tickers_returns_unique_sorted(repo):
    _seed(repo, "schwab", "personal", [
        _make_trade("schwab/personal", "TSLA", date(2024, 1, 1)),
        _make_trade("schwab/personal", "AAPL", date(2024, 1, 2)),
        _make_trade("schwab/personal", "TSLA", date(2024, 2, 1)),
    ])
    assert repo.list_distinct_tickers() == ["AAPL", "TSLA"]


def test_get_trades_for_ticker_filters_by_ticker(repo):
    _seed(repo, "schwab", "personal", [
        _make_trade("schwab/personal", "TSLA", date(2024, 1, 1)),
        _make_trade("schwab/personal", "AAPL", date(2024, 1, 2)),
        _make_trade("schwab/personal", "TSLA", date(2024, 2, 1)),
    ])
    trades = repo.get_trades_for_ticker("TSLA")
    assert len(trades) == 2
    assert all(t.ticker == "TSLA" for t in trades)


def test_get_lots_for_ticker_returns_empty_when_no_lots(repo):
    assert repo.get_lots_for_ticker("TSLA") == []


def test_get_violations_for_ticker_returns_empty_when_none(repo):
    assert repo.get_violations_for_ticker("TSLA") == []
