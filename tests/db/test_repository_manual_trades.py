from __future__ import annotations

from datetime import date

from sqlalchemy import text

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.domain import Trade


def _setup(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO accounts(broker, label) VALUES ('Schwab','Tax')"))
    return Repository(engine)


def test_create_manual_trade_persists_and_marks_is_manual(tmp_path):
    repo = _setup(tmp_path)
    t = Trade(
        account="Schwab/Tax",
        date=date(2026, 1, 15),
        ticker="AAPL",
        action="Buy",
        quantity=10,
        cost_basis=1500.0,
        basis_source="user",
        is_manual=True,
    )
    saved = repo.create_manual_trade(t, etf_pairs={})
    assert saved.id is not None
    assert saved.is_manual is True
    assert saved.basis_source == "user"
    trades = repo.all_trades()
    assert len(trades) == 1
    assert trades[0].is_manual is True


def test_create_manual_trade_uses_manual_namespace_natural_key(tmp_path):
    repo = _setup(tmp_path)
    t = Trade(
        account="Schwab/Tax",
        date=date(2026, 1, 15),
        ticker="AAPL",
        action="Buy",
        quantity=10,
        cost_basis=1500.0,
        basis_source="user",
        is_manual=True,
    )
    repo.create_manual_trade(t, etf_pairs={})
    with repo.engine.begin() as conn:
        row = conn.execute(text("SELECT natural_key FROM trades")).first()
    assert row[0].startswith("manual:")


def test_update_imported_transfer_in_keeps_natural_key(tmp_path):
    """Editing a transfer_in row updates date+basis but never natural_key."""
    repo = _setup(tmp_path)
    # Insert a transfer-in row directly (bypass parser).
    with repo.engine.begin() as conn:
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
                "VALUES (1, 1, 'csv:nk1', 'AAPL', '2026-02-01', 'Buy', 10, NULL, 'transfer_in', 0, 0, 0)"
            )
        )
        row = conn.execute(text("SELECT id FROM trades")).first()
        trade_id = str(row[0])

    repo.update_imported_transfer(
        trade_id=trade_id,
        new_date=date(2024, 6, 15),
        new_basis_or_proceeds=2500.0,
        etf_pairs={},
    )

    with repo.engine.begin() as conn:
        row = conn.execute(
            text("SELECT trade_date, cost_basis, natural_key, transfer_basis_user_set FROM trades")
        ).first()
    assert row[0] == "2024-06-15"
    assert abs(row[1] - 2500.0) < 1e-9
    assert row[2] == "csv:nk1"  # preserved
    assert row[3] == 1


def test_update_imported_transfer_rejects_non_transfer_row(tmp_path):
    repo = _setup(tmp_path)
    with repo.engine.begin() as conn:
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
                "VALUES (1, 1, 'csv:nk2', 'AAPL', '2024-06-15', 'Buy', 10, 1000, 'broker_csv', 0, 0, 0)"
            )
        )
        trade_id = str(conn.execute(text("SELECT id FROM trades")).first()[0])

    import pytest

    with pytest.raises(ValueError):
        repo.update_imported_transfer(
            trade_id=trade_id,
            new_date=date(2024, 6, 15),
            new_basis_or_proceeds=2500.0,
            etf_pairs={},
        )


def test_update_imported_transfer_out_uses_proceeds(tmp_path):
    """transfer_out rows should write to proceeds, not cost_basis."""
    repo = _setup(tmp_path)
    with repo.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO imports(account_id, csv_filename, csv_sha256, imported_at, trade_count) "
                "VALUES (1, 'x.csv', 'h', '2026-04-26T00:00:00', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO trades(import_id, account_id, natural_key, ticker, trade_date, action, "
                "quantity, proceeds, basis_source, is_manual, transfer_basis_user_set, basis_unknown) "
                "VALUES (1, 1, 'csv:nk3', 'AAPL', '2026-02-01', 'Sell', 10, NULL, 'transfer_out', 0, 0, 0)"
            )
        )
        trade_id = str(conn.execute(text("SELECT id FROM trades")).first()[0])

    repo.update_imported_transfer(
        trade_id=trade_id,
        new_date=date(2026, 2, 1),
        new_basis_or_proceeds=2700.0,
        etf_pairs={},
    )

    with repo.engine.begin() as conn:
        row = conn.execute(text("SELECT cost_basis, proceeds FROM trades")).first()
    assert row[0] is None  # cost_basis untouched
    assert abs(row[1] - 2700.0) < 1e-9  # proceeds set


def test_update_manual_trade_full_edit(tmp_path):
    repo = _setup(tmp_path)
    t = Trade(
        account="Schwab/Tax",
        date=date(2026, 1, 15),
        ticker="AAPL",
        action="Buy",
        quantity=10,
        cost_basis=1500.0,
        basis_source="user",
        is_manual=True,
    )
    saved = repo.create_manual_trade(t, etf_pairs={})

    updated = Trade(
        id=saved.id,
        account="Schwab/Tax",
        date=date(2025, 12, 20),
        ticker="AAPL",
        action="Buy",
        quantity=12,
        cost_basis=1900.0,
        basis_source="user",
        is_manual=True,
    )
    repo.update_manual_trade(updated, etf_pairs={})

    refetched = repo.all_trades()[0]
    assert refetched.date == date(2025, 12, 20)
    assert abs(refetched.quantity - 12.0) < 1e-9
    assert abs(refetched.cost_basis - 1900.0) < 1e-9


def test_update_manual_trade_rejects_imported_row(tmp_path):
    repo = _setup(tmp_path)
    with repo.engine.begin() as conn:
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
                "VALUES (1, 1, 'csv:x', 'AAPL', '2024-06-15', 'Buy', 10, 1000, 'broker_csv', 0, 0, 0)"
            )
        )
        trade_id = str(conn.execute(text("SELECT id FROM trades")).first()[0])

    t = Trade(
        id=trade_id,
        account="Schwab/Tax",
        date=date(2024, 1, 1),
        ticker="AAPL",
        action="Buy",
        quantity=10,
        cost_basis=999.0,
        basis_source="user",
        is_manual=True,
    )
    import pytest

    with pytest.raises(ValueError):
        repo.update_manual_trade(t, etf_pairs={})


def test_update_manual_trade_preserves_natural_key(tmp_path):
    """Editing a manual row must NOT regenerate its natural_key."""
    repo = _setup(tmp_path)
    saved = repo.create_manual_trade(
        Trade(
            account="Schwab/Tax",
            date=date(2026, 1, 15),
            ticker="AAPL",
            action="Buy",
            quantity=10,
            cost_basis=1500.0,
            basis_source="user",
            is_manual=True,
        ),
        etf_pairs={},
    )
    with repo.engine.begin() as conn:
        original_nk = conn.execute(text("SELECT natural_key FROM trades")).first()[0]
    assert original_nk.startswith("manual:")

    repo.update_manual_trade(
        Trade(
            id=saved.id,
            account="Schwab/Tax",
            date=date(2025, 1, 1),
            ticker="AAPL",
            action="Buy",
            quantity=99,
            cost_basis=2999.0,
            basis_source="user",
            is_manual=True,
        ),
        etf_pairs={},
    )
    with repo.engine.begin() as conn:
        nk_after = conn.execute(text("SELECT natural_key FROM trades")).first()[0]
    assert nk_after == original_nk


def test_delete_manual_trade_removes_row(tmp_path):
    repo = _setup(tmp_path)
    t = Trade(
        account="Schwab/Tax",
        date=date(2026, 1, 15),
        ticker="AAPL",
        action="Buy",
        quantity=10,
        cost_basis=1500.0,
        basis_source="user",
        is_manual=True,
    )
    saved = repo.create_manual_trade(t, etf_pairs={})
    repo.delete_manual_trade(saved.id, etf_pairs={})
    assert repo.all_trades() == []


def test_delete_manual_trade_rejects_imported_row(tmp_path):
    repo = _setup(tmp_path)
    with repo.engine.begin() as conn:
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
                "VALUES (1, 1, 'csv:x', 'AAPL', '2024-06-15', 'Buy', 10, 1000, 'broker_csv', 0, 0, 0)"
            )
        )
        trade_id = str(conn.execute(text("SELECT id FROM trades")).first()[0])

    import pytest

    with pytest.raises(ValueError):
        repo.delete_manual_trade(trade_id, etf_pairs={})


def test_delete_manual_trade_removes_associated_violation(tmp_path):
    """A wash-sale violation triggered by a manual buy should disappear when that buy is deleted."""
    repo = _setup(tmp_path)
    # Step 1: insert a loss sale (imported) so deleting the manual buy later removes the violation.
    with repo.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO imports(account_id, csv_filename, csv_sha256, imported_at, trade_count) "
                "VALUES (1, 'x.csv', 'h', '2026-04-26T00:00:00', 1)"
            )
        )
        # Loss sale on Jan 5 — sold for less than basis.
        conn.execute(
            text(
                "INSERT INTO trades(import_id, account_id, natural_key, ticker, trade_date, action, "
                "quantity, proceeds, cost_basis, basis_source, is_manual, transfer_basis_user_set, basis_unknown) "
                "VALUES (1, 1, 'csv:loss', 'AAPL', '2026-01-05', 'Sell', 10, 800, 1000, 'broker_csv', 0, 0, 0)"
            )
        )
        # Original buy lot — far enough back (>30 days) to be outside the wash window.
        conn.execute(
            text(
                "INSERT INTO trades(import_id, account_id, natural_key, ticker, trade_date, action, "
                "quantity, proceeds, cost_basis, basis_source, is_manual, transfer_basis_user_set, basis_unknown) "
                "VALUES (1, 1, 'csv:original', 'AAPL', '2025-12-01', 'Buy', 10, NULL, 1000, 'broker_csv', 0, 0, 0)"
            )
        )

    # Step 2: add a manual replacement buy WITHIN the wash window — triggers a violation.
    saved = repo.create_manual_trade(
        Trade(
            account="Schwab/Tax",
            date=date(2026, 1, 15),  # within 30 days of 2026-01-05 loss
            ticker="AAPL",
            action="Buy",
            quantity=10,
            cost_basis=900,
            basis_source="user",
            is_manual=True,
        ),
        etf_pairs={},
    )
    # Confirm a violation exists.
    with repo.engine.begin() as conn:
        n_viol = conn.execute(text("SELECT COUNT(*) FROM wash_sale_violations")).first()[0]
    assert n_viol >= 1, "expected manual buy within wash window to trigger a violation"

    # Step 3: delete the manual buy → violation should disappear after recompute.
    repo.delete_manual_trade(saved.id, etf_pairs={})
    with repo.engine.begin() as conn:
        n_viol_after = conn.execute(text("SELECT COUNT(*) FROM wash_sale_violations")).first()[0]
    assert n_viol_after == 0, f"expected violation removed after manual delete, found {n_viol_after}"
