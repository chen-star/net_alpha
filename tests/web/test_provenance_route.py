from datetime import date, datetime

from fastapi.testclient import TestClient

from net_alpha.audit.provenance import Period, RealizedPLRef, encode_metric_ref
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
        acct,
        record,
        [
            Trade(
                account="Schwab/Tax",
                date=date(2026, 4, 1),
                ticker="AAPL",
                action="Sell",
                quantity=10,
                proceeds=1500.0,
                cost_basis=1000.0,
            )
        ],
    )
    return acct


def test_provenance_route_returns_modal_fragment(tmp_path):
    acct = _seed(tmp_path)
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    ref = RealizedPLRef(
        kind="realized_pl",
        period=Period(start=date(2026, 1, 1), end=date(2027, 1, 1), label="YTD 2026"),
        account_id=acct.id,
        symbol="AAPL",
    )
    encoded = encode_metric_ref(ref)
    resp = client.get(f"/provenance/{encoded}")
    assert resp.status_code == 200
    assert "$500.00" in resp.text or "500.00" in resp.text
    assert "AAPL" in resp.text


def test_provenance_route_handles_garbage_id(tmp_path):
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    resp = client.get("/provenance/not-a-ref")
    # Renders error fragment, not a 5xx — modal must always succeed.
    assert resp.status_code == 200
    assert "Couldn't reconstruct trace" in resp.text
