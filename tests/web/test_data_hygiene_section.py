from datetime import date, datetime

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.domain import ImportRecord, Trade
from net_alpha.web.app import create_app


def test_imports_page_shows_hygiene_section_when_issues_exist(tmp_path):
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
        acct,
        record,
        [
            Trade(
                account="Schwab/Tax",
                date=date(2026, 1, 1),
                ticker="AAPL",
                action="Buy",
                quantity=10,
                cost_basis=None,
                basis_unknown=True,
                basis_source="transfer_in",
            )
        ],
    )
    client = TestClient(create_app(settings))
    resp = client.get("/imports")
    assert resp.status_code == 200
    assert "Data quality" in resp.text
    assert "AAPL" in resp.text
    assert "set-basis" in resp.text  # the inline form action


def test_imports_page_hides_hygiene_section_when_clean(tmp_path):
    settings = Settings(data_dir=tmp_path)
    client = TestClient(create_app(settings))
    resp = client.get("/imports")
    assert resp.status_code == 200
    assert "Data quality" not in resp.text
