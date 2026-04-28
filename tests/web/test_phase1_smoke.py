"""End-to-end smoke for Phase 1: provenance modal + reconciliation strip + hygiene section.

Catches integration regressions when any of the three sub-features is touched.
"""

from datetime import date, datetime

from fastapi.testclient import TestClient

from net_alpha.audit._badge_cache import _cache as _badge_cache
from net_alpha.audit.provenance import Period, RealizedPLRef, encode_metric_ref
from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.domain import CashEvent, ImportRecord, Trade
from net_alpha.models.realized_gl import RealizedGLLot
from net_alpha.web.app import create_app


def test_phase1_smoke(tmp_path):
    _badge_cache.invalidate()

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
        trade_count=4,
    )
    repo.add_import(
        acct,
        record,
        [
            Trade(
                account="Schwab/Tax", date=date(2026, 1, 1), ticker="AAPL", action="Buy", quantity=10, cost_basis=1000.0
            ),
            Trade(
                account="Schwab/Tax",
                date=date(2026, 4, 1),
                ticker="AAPL",
                action="Sell",
                quantity=10,
                proceeds=1500.0,
                cost_basis=1000.0,
            ),
            Trade(
                account="Schwab/Tax",
                date=date(2026, 4, 5),
                ticker="XYZ",
                action="Sell",
                quantity=5,
                proceeds=500.0,
                cost_basis=400.0,
            ),
            Trade(
                account="Schwab/Tax",
                date=date(2026, 1, 1),
                ticker="MSFT",
                action="Buy",
                quantity=10,
                cost_basis=None,
                basis_unknown=True,
                basis_source="transfer_in",
            ),
        ],
        cash_events=[
            CashEvent(account="Schwab/Tax", event_date=date(2026, 1, 1), kind="transfer_in", amount=10000.0),
        ],
    )
    repo.add_gl_lots(
        acct,
        import_id=1,
        lots=[
            RealizedGLLot(
                account_display="Schwab/Tax",
                symbol_raw="AAPL",
                ticker="AAPL",
                closed_date=date(2026, 4, 1),
                opened_date=date(2026, 1, 1),
                quantity=10.0,
                proceeds=1500.0,
                cost_basis=1000.0,
                unadjusted_cost_basis=1000.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Long Term",
            )
        ],
    )

    client = TestClient(create_app(settings))

    # 1) Provenance modal renders with a contributing trade.
    encoded = encode_metric_ref(
        RealizedPLRef(
            kind="realized_pl",
            period=Period(start=date(2026, 1, 1), end=date(2027, 1, 1), label="YTD 2026"),
            account_id=acct.id,
            symbol="AAPL",
        )
    )
    r1 = client.get(f"/provenance/{encoded}")
    assert r1.status_code == 200, r1.text
    assert "AAPL" in r1.text

    # 2) Reconciliation strip resolves to MATCH on AAPL.
    r2 = client.get(f"/reconciliation/AAPL?account_id={acct.id}")
    assert r2.status_code == 200, r2.text
    assert "✓" in r2.text or "match" in r2.text.lower()

    # 3) Imports page surfaces 2 issues (basis_unknown error + orphan_sell warn).
    r3 = client.get("/imports/_legacy_page")
    assert r3.status_code == 200, r3.text
    assert "Data quality" in r3.text
    assert "MSFT" in r3.text  # basis_unknown error
    assert "XYZ" in r3.text  # orphan sell

    # 4) Nav-bar badge appears on every page (one error → badge).
    r4 = client.get("/")
    assert 'data-testid="imports-badge"' in r4.text
