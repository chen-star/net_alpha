from __future__ import annotations

from datetime import date

from net_alpha.models.domain import Trade
from net_alpha.web.format import display_action


def _t(action="Buy", basis_source="broker_csv"):
    return Trade(
        account="Schwab/Tax",
        date=date(2026, 1, 15),
        ticker="AAPL",
        action=action,
        quantity=10,
        basis_source=basis_source,
    )


def test_display_action_transfer_in():
    assert display_action(_t(action="Buy", basis_source="transfer_in")) == "Transfer In"


def test_display_action_transfer_out():
    assert display_action(_t(action="Sell", basis_source="transfer_out")) == "Transfer Out"


def test_display_action_regular_buy():
    assert display_action(_t(action="Buy", basis_source="broker_csv")) == "Buy"


def test_display_action_regular_sell():
    assert display_action(_t(action="Sell", basis_source="broker_csv")) == "Sell"


def test_display_action_user_manual_buy():
    assert display_action(_t(action="Buy", basis_source="user")) == "Buy"


def test_ticker_timeline_renders_transfer_in_label(tmp_path):
    """A transfer_in row in the Timeline should render 'Transfer In', not 'Buy'."""
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from net_alpha.config import Settings
    from net_alpha.db.connection import get_engine, init_db
    from net_alpha.web.app import create_app

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
                "VALUES (1, 1, 'csv:t1', 'AAPL', '2026-02-01', 'Buy', 10, NULL, 'transfer_in', 0, 0, 0)"
            )
        )
    client = TestClient(create_app(settings))
    response = client.get("/ticker/AAPL")
    assert response.status_code == 200
    html = response.text
    assert "Transfer In" in html
