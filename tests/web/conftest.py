from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.domain import Account, ImportRecord, OptionDetails, Trade
from net_alpha.web.app import create_app

# Skip scheduler startup in all web tests — it requires a running asyncio
# event loop (AsyncIOScheduler) and service infrastructure not available in
# sync test environments.
os.environ.setdefault("NETALPHA_SKIP_SCHEDULER", "1")


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


@pytest.fixture()
def repo_real(settings):
    from net_alpha.db.connection import get_engine
    from net_alpha.db.repository import Repository

    return Repository(get_engine(settings.db_path))


@pytest.fixture
def client(settings: Settings, engine) -> TestClient:
    """TestClient with the app pointed at the temp DB."""
    app = create_app(settings)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def tmp_data_dir(settings: Settings) -> Path:
    """Path to the per-test data dir (alias for ``settings.data_dir``)."""
    return settings.data_dir


@pytest.fixture
def client_with_data(client: TestClient, settings: Settings) -> TestClient:
    """TestClient with the real DB pre-seeded by the demo fixture builder.

    Used in tests that need 'imports already exist' state in the real DB.
    """
    from net_alpha.web.demo import build_demo_db

    build_demo_db(settings.db_path)
    return client


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


def make_sto(
    account_display: str,
    ticker: str,
    day: date,
    *,
    strike: float,
    expiry: date,
    call_put: str,
    qty: float = 1.0,
    proceeds: float = 100.0,
) -> Trade:
    """Sell-To-Open of a short option (premium received)."""
    return Trade(
        account=account_display,
        date=day,
        ticker=ticker,
        action="Sell",
        quantity=qty,
        proceeds=proceeds,
        cost_basis=None,
        basis_source="option_short_open",
        option_details=OptionDetails(strike=strike, expiry=expiry, call_put=call_put),
    )


def make_btc(
    account_display: str,
    ticker: str,
    day: date,
    *,
    strike: float,
    expiry: date,
    call_put: str,
    qty: float = 1.0,
    cost: float = 5.0,
) -> Trade:
    """Buy-To-Close of a short option."""
    return Trade(
        account=account_display,
        date=day,
        ticker=ticker,
        action="Buy",
        quantity=qty,
        proceeds=None,
        cost_basis=cost,
        basis_source="option_short_close",
        option_details=OptionDetails(strike=strike, expiry=expiry, call_put=call_put),
    )


def make_bto(
    account_display: str,
    ticker: str,
    day: date,
    *,
    strike: float,
    expiry: date,
    call_put: str,
    qty: float = 1.0,
    cost: float = 100.0,
) -> Trade:
    """Buy-To-Open a long option."""
    return Trade(
        account=account_display,
        date=day,
        ticker=ticker,
        action="Buy",
        quantity=qty,
        proceeds=None,
        cost_basis=cost,
        option_details=OptionDetails(strike=strike, expiry=expiry, call_put=call_put),
    )


def make_stc(
    account_display: str,
    ticker: str,
    day: date,
    *,
    strike: float,
    expiry: date,
    call_put: str,
    qty: float = 1.0,
    proceeds: float = 80.0,
    cost: float = 100.0,
) -> Trade:
    """Sell-To-Close a long option."""
    return Trade(
        account=account_display,
        date=day,
        ticker=ticker,
        action="Sell",
        quantity=qty,
        proceeds=proceeds,
        cost_basis=cost,
        option_details=OptionDetails(strike=strike, expiry=expiry, call_put=call_put),
    )


def make_assigned_close(
    account_display: str,
    ticker: str,
    day: date,
    *,
    strike: float,
    expiry: date,
    call_put: str,
    qty: float = 1.0,
) -> Trade:
    """The synthetic 'option_short_close_assigned' close paired with put_assignment."""
    return Trade(
        account=account_display,
        date=day,
        ticker=ticker,
        action="Buy",
        quantity=qty,
        proceeds=None,
        cost_basis=0.0,
        basis_source="option_short_close_assigned",
        option_details=OptionDetails(strike=strike, expiry=expiry, call_put=call_put),
    )


def make_put_assignment(
    account_display: str,
    ticker: str,
    day: date,
    *,
    qty: float,
    cost: float,
) -> Trade:
    """Stock BUY produced by a put assignment."""
    return Trade(
        account=account_display,
        date=day,
        ticker=ticker,
        action="Buy",
        quantity=qty,
        proceeds=None,
        cost_basis=cost,
        basis_source="put_assignment",
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
            "make_sto": staticmethod(make_sto),
            "make_btc": staticmethod(make_btc),
            "make_bto": staticmethod(make_bto),
            "make_stc": staticmethod(make_stc),
            "make_assigned_close": staticmethod(make_assigned_close),
            "make_put_assignment": staticmethod(make_put_assignment),
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
