from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import text

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.web.app import create_app


def _client(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO accounts(broker, label) VALUES ('Schwab','Tax')"))
        # The /imports list is the source of truth for accounts known to the
        # validator. Insert a dummy import so the account label appears there.
        conn.execute(text(
            "INSERT INTO imports(account_id, csv_filename, csv_sha256, imported_at, trade_count) "
            "VALUES (1, 'x.csv', 'h', '2026-04-26T00:00:00', 0)"
        ))
    return TestClient(create_app(settings))


def test_post_trades_creates_manual_buy(tmp_path):
    client = _client(tmp_path)
    r = client.post(
        "/trades",
        data={
            "account": "Schwab/Tax",
            "ticker": "AAPL",
            "trade_date": "2026-01-15",
            "action_choice": "Buy",
            "quantity": "10",
            "basis_or_proceeds": "1500",
        },
        follow_redirects=False,
    )
    assert r.status_code in (200, 303)
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    with engine.begin() as conn:
        row = conn.execute(text(
            "SELECT ticker, action, basis_source, is_manual, cost_basis FROM trades"
        )).first()
    assert row[0] == "AAPL"
    assert row[1] == "Buy"
    assert row[2] == "user"
    assert row[3] == 1
    assert abs(row[4] - 1500.0) < 1e-9


def test_post_trades_creates_manual_transfer_in(tmp_path):
    """Transfer In selection stores action=Buy + basis_source=transfer_in."""
    client = _client(tmp_path)
    r = client.post(
        "/trades",
        data={
            "account": "Schwab/Tax",
            "ticker": "AAPL",
            "trade_date": "2024-06-15",
            "action_choice": "Transfer In",
            "quantity": "10",
            "basis_or_proceeds": "2500",
        },
        follow_redirects=False,
    )
    assert r.status_code in (200, 303)
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    with engine.begin() as conn:
        row = conn.execute(text(
            "SELECT action, basis_source, is_manual, cost_basis FROM trades"
        )).first()
    assert row[0] == "Buy"
    assert row[1] == "transfer_in"
    assert row[2] == 1
    assert abs(row[3] - 2500.0) < 1e-9


def test_post_trades_rejects_unknown_account(tmp_path):
    client = _client(tmp_path)
    r = client.post(
        "/trades",
        data={
            "account": "Schwab/Bogus",
            "ticker": "AAPL",
            "trade_date": "2026-01-15",
            "action_choice": "Buy",
            "quantity": "10",
            "basis_or_proceeds": "1500",
        },
    )
    assert r.status_code == 400


def test_post_trades_rejects_future_date(tmp_path):
    from datetime import date, timedelta
    client = _client(tmp_path)
    future = (date.today() + timedelta(days=30)).isoformat()
    r = client.post(
        "/trades",
        data={
            "account": "Schwab/Tax",
            "ticker": "AAPL",
            "trade_date": future,
            "action_choice": "Buy",
            "quantity": "10",
            "basis_or_proceeds": "1500",
        },
    )
    assert r.status_code == 400
