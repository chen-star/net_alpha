from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import text

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine
from net_alpha.web.app import create_app


def _client(tmp_path):
    return TestClient(create_app(Settings(data_dir=tmp_path)))


def _seed_import(tmp_path) -> None:
    """Insert one stub import so the page renders with data."""
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO accounts(broker, label) VALUES ('Schwab', 'Tax')"))
        conn.execute(
            text(
                "INSERT INTO imports(account_id, csv_filename, csv_sha256, imported_at, trade_count) "
                "VALUES (1, 'x.csv', 'h', '2026-04-26T00:00:00', 0)"
            )
        )


def test_holdings_page_returns_200(tmp_path):
    client = _client(tmp_path)  # creates app + initialises DB tables
    _seed_import(tmp_path)
    response = client.get("/holdings")
    assert response.status_code == 200
    # The page wires the existing positions fragment.
    assert "/portfolio/positions" in response.text
    assert 'id="holdings-positions"' in response.text


def test_holdings_page_active_in_nav(tmp_path):
    client = _client(tmp_path)
    response = client.get("/holdings")
    assert response.status_code == 200
    assert ">Holdings<" in response.text
    assert 'class="nav-link active"' in response.text


def test_holdings_link_appears_on_other_pages(tmp_path):
    client = _client(tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    assert ">Holdings<" in response.text
