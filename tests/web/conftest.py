from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.domain import Account, ImportRecord, Trade
from net_alpha.web.app import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings pointing at a temp data dir for full test isolation."""
    return Settings(data_dir=tmp_path)


@pytest.fixture
def engine(settings: Settings):
    """Engine bound to the temp DB. Uses init_db so the schema matches
    production (includes hand-written migration tables like
    historical_price_cache that aren't in SQLModel.metadata)."""
    eng = get_engine(settings.db_path)
    init_db(eng)
    return eng


@pytest.fixture
def repo(engine) -> Repository:
    """Repository ready for direct seeding from tests."""
    return Repository(engine)


@pytest.fixture
def client(settings: Settings, engine) -> TestClient:
    """TestClient with the app pointed at the temp DB."""
    app = create_app(settings)
    return TestClient(app, raise_server_exceptions=False)


# --- Trade builders ---------------------------------------------------------


def make_buy(
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


def make_sell(
    account_display: str,
    ticker: str,
    day: date,
    qty: float = 10.0,
    proceeds: float = 1500.0,
    cost: float = 1800.0,
) -> Trade:
    return Trade(
        account=account_display,
        date=day,
        ticker=ticker,
        action="Sell",
        quantity=qty,
        proceeds=proceeds,
        cost_basis=cost,
    )


def seed_import(
    repo: Repository,
    broker: str,
    label: str,
    trades: list[Trade],
    csv_filename: str = "seed.csv",
) -> tuple[Account, int]:
    """Create the account, build an ImportRecord, and call repo.add_import.

    Returns (account, import_id).
    """
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
            "make_buy": staticmethod(make_buy),
            "make_sell": staticmethod(make_sell),
            "seed_import": staticmethod(seed_import),
        },
    )


@pytest.fixture
def seed_transfer_in(repo):
    """Seed one transfer_in trade with no basis. Returns
    (sym, account_id, trade_id, qty, transfer_date).

    Marks is_manual=False so the row is treated as an imported transfer
    (which is what the inline set-basis form is for)."""
    repo.get_or_create_account("Schwab", "x")
    trade = Trade(
        account="Schwab/x",
        date=date(2026, 2, 1),
        ticker="AAPL",
        action="Buy",
        quantity=100.0,
        proceeds=None,
        cost_basis=None,
        gross_cash_impact=None,
        basis_source="transfer_in",
        option_details=None,
    )
    saved = repo.create_manual_trade(trade, etf_pairs={})
    repo._set_is_manual_for_test(int(saved.id), False)
    account_id = repo.list_accounts()[0].id
    return ("AAPL", account_id, str(saved.id), 100.0, date(2026, 2, 1))
