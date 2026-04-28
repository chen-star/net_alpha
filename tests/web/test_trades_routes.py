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
        conn.execute(
            text(
                "INSERT INTO imports(account_id, csv_filename, csv_sha256, imported_at, trade_count) "
                "VALUES (1, 'x.csv', 'h', '2026-04-26T00:00:00', 0)"
            )
        )
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
        row = conn.execute(text("SELECT ticker, action, basis_source, is_manual, cost_basis FROM trades")).first()
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
        row = conn.execute(text("SELECT action, basis_source, is_manual, cost_basis FROM trades")).first()
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


def test_edit_transfer_updates_imported_row(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO accounts(broker, label) VALUES ('Schwab','Tax')"))
        conn.execute(
            text(
                "INSERT INTO imports(account_id, csv_filename, csv_sha256, imported_at, trade_count) "
                "VALUES (1, 'x.csv', 'h', '2026-04-26T00:00:00', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO trades(import_id, account_id, natural_key, ticker, trade_date, action, "
                "quantity, cost_basis, basis_source, is_manual, transfer_basis_user_set, basis_unknown) "
                "VALUES (1, 1, 'csv:k1', 'AAPL', '2026-02-01', 'Buy', 10, NULL, 'transfer_in', 0, 0, 0)"
            )
        )
        trade_id = conn.execute(text("SELECT id FROM trades")).first()[0]
    client = TestClient(create_app(settings))
    r = client.post(
        f"/trades/{trade_id}/edit-transfer",
        data={"seg_date": "2024-06-15", "seg_qty": "10", "seg_basis": "2500"},
        follow_redirects=False,
    )
    assert r.status_code in (200, 303)
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT trade_date, cost_basis, transfer_basis_user_set, natural_key FROM trades")
        ).first()
    assert row[0] == "2024-06-15"
    assert abs(row[1] - 2500.0) < 1e-9
    assert row[2] == 1
    assert row[3] == "csv:k1"  # natural_key preserved


def test_edit_transfer_rejects_non_transfer_row(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO accounts(broker, label) VALUES ('Schwab','Tax')"))
        conn.execute(
            text(
                "INSERT INTO imports(account_id, csv_filename, csv_sha256, imported_at, trade_count) "
                "VALUES (1, 'x.csv', 'h', '2026-04-26T00:00:00', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO trades(import_id, account_id, natural_key, ticker, trade_date, action, "
                "quantity, cost_basis, basis_source, is_manual, transfer_basis_user_set, basis_unknown) "
                "VALUES (1, 1, 'csv:k2', 'AAPL', '2024-06-15', 'Buy', 10, 1000, 'broker_csv', 0, 0, 0)"
            )
        )
        trade_id = conn.execute(text("SELECT id FROM trades")).first()[0]
    client = TestClient(create_app(settings))
    r = client.post(
        f"/trades/{trade_id}/edit-transfer",
        data={"seg_date": "2024-06-15", "seg_qty": "10", "seg_basis": "2500"},
    )
    assert r.status_code == 400


def test_edit_transfer_splits_into_multiple_segments(tmp_path):
    """Posting parallel arrays of seg_* fields splits the parent into N siblings."""
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO accounts(broker, label) VALUES ('Schwab','Tax')"))
        conn.execute(
            text(
                "INSERT INTO imports(account_id, csv_filename, csv_sha256, imported_at, trade_count) "
                "VALUES (1, 'x.csv', 'h', '2026-04-26T00:00:00', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO trades(import_id, account_id, natural_key, ticker, trade_date, action, "
                "quantity, cost_basis, basis_source, is_manual, transfer_basis_user_set, basis_unknown, "
                "transfer_date) VALUES (1, 1, 'csv:k3', 'AAPL', '2026-02-01', 'Buy', 30, NULL, "
                "'transfer_in', 0, 0, 0, '2026-02-01')"
            )
        )
        trade_id = conn.execute(text("SELECT id FROM trades")).first()[0]
    client = TestClient(create_app(settings))
    r = client.post(
        f"/trades/{trade_id}/edit-transfer",
        data={
            "seg_date": ["2023-01-15", "2024-03-01", "2024-09-30"],
            "seg_qty": ["10", "10", "10"],
            "seg_basis": ["1000", "1500", "2000"],
        },
        follow_redirects=False,
    )
    assert r.status_code in (200, 303)
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT trade_date, quantity, cost_basis, transfer_date, transfer_group_id, natural_key "
                "FROM trades ORDER BY trade_date"
            )
        ).all()
    assert len(rows) == 3
    # All siblings share the same transfer_date (broker statement) and group id.
    group_ids = {r[4] for r in rows}
    xfer_dates = {r[3] for r in rows}
    assert len(group_ids) == 1 and next(iter(group_ids)) is not None
    assert xfer_dates == {"2026-02-01"}
    # Acquisition dates and basis match the input.
    assert [r[0] for r in rows] == ["2023-01-15", "2024-03-01", "2024-09-30"]
    assert [r[1] for r in rows] == [10.0, 10.0, 10.0]
    assert [r[2] for r in rows] == [1000.0, 1500.0, 2000.0]
    # First segment kept the original natural_key for re-import dedup;
    # the others got derived suffixes.
    nks = sorted(r[5] for r in rows)
    assert "csv:k3" in nks
    assert any(nk.startswith("csv:k3:seg") for nk in nks)


def test_edit_transfer_rejects_qty_mismatch(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO accounts(broker, label) VALUES ('Schwab','Tax')"))
        conn.execute(
            text(
                "INSERT INTO imports(account_id, csv_filename, csv_sha256, imported_at, trade_count) "
                "VALUES (1, 'x.csv', 'h', '2026-04-26T00:00:00', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO trades(import_id, account_id, natural_key, ticker, trade_date, action, "
                "quantity, cost_basis, basis_source, is_manual, transfer_basis_user_set, basis_unknown) "
                "VALUES (1, 1, 'csv:k4', 'AAPL', '2026-02-01', 'Buy', 30, NULL, 'transfer_in', 0, 0, 0)"
            )
        )
        trade_id = conn.execute(text("SELECT id FROM trades")).first()[0]
    client = TestClient(create_app(settings))
    r = client.post(
        f"/trades/{trade_id}/edit-transfer",
        data={
            "seg_date": ["2024-01-01", "2024-02-01"],
            "seg_qty": ["10", "10"],  # sums to 20, parent is 30
            "seg_basis": ["1000", "1000"],
        },
    )
    assert r.status_code == 400


def test_edit_manual_updates_user_row(tmp_path):
    client = _client(tmp_path)
    # Create a manual trade first.
    client.post(
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
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    with engine.begin() as conn:
        trade_id = conn.execute(text("SELECT id FROM trades")).first()[0]
    r = client.post(
        f"/trades/{trade_id}/edit-manual",
        data={
            "account": "Schwab/Tax",
            "ticker": "AAPL",
            "trade_date": "2025-12-20",
            "action_choice": "Buy",
            "quantity": "12",
            "basis_or_proceeds": "1900",
        },
        follow_redirects=False,
    )
    assert r.status_code in (200, 303)
    with engine.begin() as conn:
        row = conn.execute(text("SELECT trade_date, quantity, cost_basis, is_manual FROM trades")).first()
    assert row[0] == "2025-12-20"
    assert abs(row[1] - 12.0) < 1e-9
    assert abs(row[2] - 1900.0) < 1e-9
    assert row[3] == 1


def test_edit_manual_rejects_imported_row(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO accounts(broker, label) VALUES ('Schwab','Tax')"))
        conn.execute(
            text(
                "INSERT INTO imports(account_id, csv_filename, csv_sha256, imported_at, trade_count) "
                "VALUES (1, 'x.csv', 'h', '2026-04-26T00:00:00', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO trades(import_id, account_id, natural_key, ticker, trade_date, action, "
                "quantity, cost_basis, basis_source, is_manual, transfer_basis_user_set, basis_unknown) "
                "VALUES (1, 1, 'csv:k', 'AAPL', '2024-06-15', 'Buy', 10, 1000, 'broker_csv', 0, 0, 0)"
            )
        )
        trade_id = conn.execute(text("SELECT id FROM trades")).first()[0]
    client = TestClient(create_app(settings))
    r = client.post(
        f"/trades/{trade_id}/edit-manual",
        data={
            "account": "Schwab/Tax",
            "ticker": "AAPL",
            "trade_date": "2024-01-01",
            "action_choice": "Buy",
            "quantity": "10",
            "basis_or_proceeds": "999",
        },
    )
    assert r.status_code == 400


def test_delete_manual_removes_row(tmp_path):
    client = _client(tmp_path)
    client.post(
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
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    with engine.begin() as conn:
        trade_id = conn.execute(text("SELECT id FROM trades")).first()[0]
    r = client.post(f"/trades/{trade_id}/delete", follow_redirects=False)
    assert r.status_code in (200, 303)
    with engine.begin() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM trades")).first()[0]
    assert n == 0


def test_delete_imported_row_rejected(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO accounts(broker, label) VALUES ('Schwab','Tax')"))
        conn.execute(
            text(
                "INSERT INTO imports(account_id, csv_filename, csv_sha256, imported_at, trade_count) "
                "VALUES (1, 'x.csv', 'h', '2026-04-26T00:00:00', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO trades(import_id, account_id, natural_key, ticker, trade_date, action, "
                "quantity, cost_basis, basis_source, is_manual, transfer_basis_user_set, basis_unknown) "
                "VALUES (1, 1, 'csv:k', 'AAPL', '2024-06-15', 'Buy', 10, 1000, 'broker_csv', 0, 0, 0)"
            )
        )
        trade_id = conn.execute(text("SELECT id FROM trades")).first()[0]
    client = TestClient(create_app(settings))
    r = client.post(f"/trades/{trade_id}/delete")
    assert r.status_code == 400
