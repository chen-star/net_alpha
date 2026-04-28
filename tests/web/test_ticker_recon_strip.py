from datetime import date, datetime

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.domain import ImportRecord, Trade
from net_alpha.web.app import create_app


def test_ticker_page_includes_reconciliation_strip(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)
    acct = repo.get_or_create_account(broker="Schwab", label="Tax")
    record = ImportRecord(
        account_id=acct.id, csv_filename="t.csv", csv_sha256="h",
        imported_at=datetime.now(), trade_count=1,
    )
    repo.add_import(
        acct, record,
        [Trade(account="Schwab/Tax", date=date(2026, 1, 1), ticker="AAPL",
               action="Buy", quantity=10, cost_basis=1000.0)],
    )
    client = TestClient(create_app(settings))
    resp = client.get("/ticker/AAPL")
    assert resp.status_code == 200
    # Strip is loaded lazily via HTMX so the page should reference the endpoint.
    assert "/reconciliation/AAPL" in resp.text
