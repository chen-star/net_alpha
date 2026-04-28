from __future__ import annotations

from datetime import date, datetime

from fastapi.testclient import TestClient

from net_alpha.db.repository import Repository
from net_alpha.models.domain import ImportRecord
from net_alpha.models.realized_gl import RealizedGLLot


def test_imports_table_renders_gl_summary_for_zero_trade_imports(client: TestClient, repo: Repository):
    acct = repo.get_or_create_account("schwab", "personal")
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="gl.csv",
        csv_sha256="abc",
        imported_at=datetime(2026, 4, 25),
        trade_count=0,
    )
    result = repo.add_import(acct, rec, [])
    # Manually insert one G/L lot into this import
    repo.add_gl_lots(
        acct,
        result.import_id,
        [
            RealizedGLLot(
                account_display=acct.display(),
                symbol_raw="WRD",
                ticker="WRD",
                closed_date=date(2026, 4, 20),
                opened_date=date(2026, 2, 11),
                quantity=100.0,
                proceeds=800.0,
                cost_basis=800.0,
                unadjusted_cost_basis=800.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Short Term",
            ),
        ],
    )
    resp = client.get("/imports/_legacy_page")
    assert resp.status_code == 200
    body = resp.text
    assert "gl.csv" in body
    # The page should now mention the G/L lot count somewhere on this row
    assert "1" in body and ("g/l" in body.lower() or "lot" in body.lower())
