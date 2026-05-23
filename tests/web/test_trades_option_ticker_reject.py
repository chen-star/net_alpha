"""Manual trade entry must reject option-shaped tickers (audit #19).

The manual trade form has only ticker/qty/basis/date/action — no strike,
expiry, or call/put inputs. Before the fix the route would happily persist
a ``Trade(option_details=None)`` even when the ticker was an option contract
symbol (e.g. ``"SPY 250117C500"`` or OCC ``"AAPL250117C150000"``), corrupting
downstream P&L. The fix validates the ticker against a plain equity-symbol
regex and rejects anything that doesn't match.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.web.app import create_app


@pytest.fixture
def client(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO accounts(broker, label) VALUES ('Schwab','Tax')"))
        conn.execute(
            text(
                "INSERT INTO imports(account_id, csv_filename, csv_sha256, imported_at, trade_count) "
                "VALUES (1, 'x.csv', 'h', '2026-04-26T00:00:00', 0)"
            )
        )
    return TestClient(create_app(settings), raise_server_exceptions=False), engine


def _post(client_obj, ticker: str):
    return client_obj.post(
        "/trades",
        data={
            "account": "Schwab/Tax",
            "ticker": ticker,
            "trade_date": "2026-01-15",
            "action_choice": "Buy",
            "quantity": "10",
            "basis_or_proceeds": "1500",
        },
        follow_redirects=False,
    )


def _trades_in_db(engine) -> int:
    with engine.begin() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM trades")).scalar_one()


def test_post_rejects_schwab_human_option_ticker(client):
    """Schwab human-format option strings (e.g. ``SPY 250117C500``)."""
    cli, engine = client
    r = _post(cli, "SPY 250117C500")
    assert r.status_code == 400
    assert "option" in r.text.lower()
    assert _trades_in_db(engine) == 0


def test_post_rejects_occ_option_ticker(client):
    """OCC 21-char ticker — long digit run after the root."""
    cli, engine = client
    r = _post(cli, "AAPL250117C150000")
    assert r.status_code == 400
    assert _trades_in_db(engine) == 0


def test_post_accepts_plain_equity_ticker(client):
    cli, engine = client
    r = _post(cli, "SPY")
    assert r.status_code in (200, 303)
    assert _trades_in_db(engine) == 1


def test_post_accepts_dot_class_share_ticker(client):
    """Berkshire-Hathaway B shares (``BRK.B``) and friends must still pass."""
    cli, engine = client
    r = _post(cli, "BRK.B")
    assert r.status_code in (200, 303)
    assert _trades_in_db(engine) == 1


def test_edit_manual_rejects_option_shaped_ticker(client, tmp_path):
    """The same validation applies to /trades/{id}/edit-manual so a user can't
    mutate a clean equity row into a corrupt option-shaped one."""
    cli, engine = client
    # Seed one valid trade so we have an id to edit.
    r = _post(cli, "MSFT")
    assert r.status_code in (200, 303)
    with engine.begin() as conn:
        trade_id = conn.execute(text("SELECT id FROM trades")).scalar_one()

    edit = cli.post(
        f"/trades/{trade_id}/edit-manual",
        data={
            "account": "Schwab/Tax",
            "ticker": "MSFT 250117C500",
            "trade_date": "2026-01-15",
            "action_choice": "Buy",
            "quantity": "10",
            "basis_or_proceeds": "1500",
        },
        follow_redirects=False,
    )
    assert edit.status_code == 400
    assert "option" in edit.text.lower()
    # Original MSFT row untouched.
    with engine.begin() as conn:
        ticker = conn.execute(text("SELECT ticker FROM trades WHERE id = :i").bindparams(i=trade_id)).scalar_one()
    assert ticker == "MSFT"
