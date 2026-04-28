from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from sqlalchemy import text

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine
from net_alpha.web.app import create_app

# A minimal Schwab Transaction History CSV with one Security Transfer row.
# The parser maps this to a Buy with basis_source='transfer_in' and basis=None.
# Headers match what SchwabParser.detect() requires:
# REQUIRED_HEADERS = {"Date", "Action", "Symbol", "Quantity", "Amount"}
# Extra columns (Description, Price, Fees & Comm) are ignored by the parser.
# Price is left blank so cost_basis stays None (broker didn't supply it).
_CSV = b"""Date,Action,Symbol,Description,Quantity,Price,Fees & Comm,Amount
01/15/2026,Security Transfer,AAPL,APPLE INC,10,,,
"""


def test_reimport_preserves_user_edits_to_transfer_row(tmp_path):
    settings = Settings(data_dir=tmp_path)
    client = TestClient(create_app(settings))

    # First import.
    r = client.post(
        "/imports",
        data={"account": "Tax"},
        files={"files": ("schwab.csv", BytesIO(_CSV), "text/csv")},
    )
    assert r.status_code in (200, 303)
    engine = get_engine(settings.db_path)
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, trade_date, cost_basis, natural_key, basis_source FROM trades")).all()
    # If the import produced 0 rows, the parser didn't recognize the CSV.
    # Inspect tests/web/fixtures/schwab_minimal.csv and adjust _CSV's header line.
    assert len(rows) == 1, f"expected 1 trade row after import, got {len(rows)}"
    trade_id, _original_date, original_basis, original_nk, src = rows[0]
    assert src == "transfer_in"
    assert original_basis is None  # broker didn't supply basis

    # User fixes date (acquisition date) and basis.
    r = client.post(
        f"/trades/{trade_id}/edit-transfer",
        data={"seg_date": "2024-06-15", "seg_qty": "10", "seg_basis": "2500"},
        follow_redirects=False,
    )
    assert r.status_code in (200, 303)
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT trade_date, cost_basis, natural_key, transfer_basis_user_set FROM trades")
        ).first()
    assert row[0] == "2024-06-15"
    assert abs(row[1] - 2500.0) < 1e-9
    assert row[2] == original_nk  # immutable
    assert row[3] == 1

    # Re-import the same CSV: idempotency should skip the row.
    r = client.post(
        "/imports",
        data={"account": "Tax"},
        files={"files": ("schwab.csv", BytesIO(_CSV), "text/csv")},
    )
    assert r.status_code in (200, 303)

    # The re-import should record the row as a duplicate, not a new trade.
    with engine.begin() as conn:
        imp_rows = conn.execute(text("SELECT trade_count, duplicate_trades FROM imports ORDER BY id")).all()
    assert len(imp_rows) == 2
    assert imp_rows[0][0] == 1  # first import: 1 new trade
    assert imp_rows[1][0] == 0  # second import: 0 new trades
    assert imp_rows[1][1] >= 1  # second import: at least 1 dup

    with engine.begin() as conn:
        rows = conn.execute(text("SELECT trade_date, cost_basis, natural_key FROM trades")).all()
    assert len(rows) == 1, f"expected 1 row after re-import (no duplicate); got {len(rows)}"
    assert rows[0][0] == "2024-06-15"  # user's date survived
    assert abs(rows[0][1] - 2500.0) < 1e-9  # user's basis survived
    assert rows[0][2] == original_nk
