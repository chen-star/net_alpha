from __future__ import annotations

from datetime import date, datetime

from net_alpha.models.domain import ImportRecord, Trade
from net_alpha.models.realized_gl import RealizedGLLot


def _seed(repo):
    acct = repo.get_or_create_account("schwab", "personal")
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="t.csv",
        csv_sha256="abc",
        imported_at=datetime(2026, 4, 25),
        trade_count=1,
    )
    repo.add_import(
        acct,
        rec,
        [
            Trade(
                account=acct.display(),
                date=date(2026, 4, 20),
                ticker="WRD",
                action="Sell",
                quantity=100,
                proceeds=800.0,
            ),
        ],
    )
    repo.add_gl_lots(
        acct,
        repo.list_imports()[0].id,
        [
            RealizedGLLot(
                account_display=acct.display(),
                symbol_raw="WRD",
                ticker="WRD",
                closed_date=date(2026, 4, 20),
                opened_date=date(2026, 2, 11),
                quantity=100.0,
                proceeds=824.96,
                cost_basis=800.66,
                unadjusted_cost_basis=800.66,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Short Term",
            ),
        ],
    )
    return acct


def test_ticker_page_renders_schwab_lot_detail_when_present(client, repo):
    _seed(repo)
    resp = client.get("/ticker/WRD")
    assert resp.status_code == 200
    assert "Schwab Lot Detail" in resp.text
    assert "800.66" in resp.text


def test_ticker_page_omits_panel_when_no_gl(client, repo):
    """No G/L data → panel doesn't render."""
    acct = repo.get_or_create_account("schwab", "personal")
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="t.csv",
        csv_sha256="abc",
        imported_at=datetime(2026, 4, 25),
        trade_count=1,
    )
    repo.add_import(
        acct,
        rec,
        [
            Trade(
                account=acct.display(),
                date=date(2026, 4, 20),
                ticker="ZZZ",
                action="Sell",
                quantity=1,
                proceeds=10.0,
            ),
        ],
    )
    resp = client.get("/ticker/ZZZ")
    assert resp.status_code == 200
    assert "Schwab Lot Detail" not in resp.text
