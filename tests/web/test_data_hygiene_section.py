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
    resp = client.get("/imports/_legacy_page")
    assert resp.status_code == 200
    # Phase 3 (I1): basis_unknown rows move to the "Missing cost basis" section
    # with a single explanation card and per-row inline forms.  The ticker
    # appears in the inline form; the old "Data quality" panel no longer shows
    # basis_unknown rows (they're excluded via the `other_issues` filter).
    assert "Missing cost basis" in resp.text
    assert "AAPL" in resp.text
    assert 'data-testid="hygiene-explanation"' in resp.text
    assert 'hx-post="/audit/set-basis?caller=drawer"' in resp.text


def test_imports_page_hides_hygiene_section_when_clean(tmp_path):
    settings = Settings(data_dir=tmp_path)
    client = TestClient(create_app(settings))
    resp = client.get("/imports/_legacy_page")
    assert resp.status_code == 200
    assert "Data quality" not in resp.text
