from datetime import date, datetime

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.domain import ImportRecord, Trade
from net_alpha.web.app import create_app


def test_set_basis_updates_trade_and_returns_swap_fragment(tmp_path):
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
    # Get the DB-assigned trade id.
    trade = next(iter(repo.all_trades()))

    client = TestClient(create_app(settings))
    resp = client.post("/audit/set-basis", data={"trade_id": trade.id, "cost_basis": "1234.56"})
    assert resp.status_code == 200
    assert "saved" in resp.text.lower()

    # Verify DB state.
    repo2 = Repository(get_engine(settings.db_path))
    updated = next(t for t in repo2.all_trades() if t.id == trade.id)
    assert updated.cost_basis == 1234.56
    assert updated.basis_unknown is False
