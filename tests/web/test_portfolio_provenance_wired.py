from datetime import date, datetime

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.domain import ImportRecord, Trade
from net_alpha.web.app import create_app


def _seed(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)
    acct = repo.get_or_create_account(broker="Schwab", label="Tax")
    record = ImportRecord(
        account_id=acct.id,
        csv_filename="t.csv",
        csv_sha256="h",
        imported_at=datetime.now(),
        trade_count=1,
    )
    repo.add_import(
        acct, record,
        [Trade(account="Schwab/Tax", date=date(2026, 4, 1), ticker="AAPL",
               action="Sell", quantity=10, proceeds=1500.0, cost_basis=1000.0)],
    )


def test_portfolio_kpis_have_provenance_triggers(tmp_path):
    _seed(tmp_path)
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    # Fragment endpoint — provenance triggers must be present.
    resp = client.get("/portfolio/body?period=ytd")
    assert resp.status_code == 200
    assert "provenance-trigger" in resp.text
    # Dialog lives in base.html; verify it appears on the full page too.
    full = client.get("/")
    assert full.status_code == 200
    assert 'id="provenance-dialog"' in full.text


def test_provenance_dialog_present_on_empty_page(tmp_path):
    """The dialog mount-point lives in base.html so it appears on every page,
    even the empty state where no KPI triggers exist yet."""
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'id="provenance-dialog"' in resp.text


def test_ticker_page_has_provenance_triggers(tmp_path):
    _seed(tmp_path)
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    resp = client.get("/ticker/AAPL")
    assert resp.status_code == 200
    assert 'id="provenance-dialog"' in resp.text
    # At least one trigger appears (the per-symbol Realized P/L number).
    assert "provenance-trigger" in resp.text
