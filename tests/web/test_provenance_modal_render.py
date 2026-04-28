from datetime import date, datetime

from fastapi.testclient import TestClient

from net_alpha.audit.provenance import Period, WashImpactRef, encode_metric_ref
from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.domain import ImportRecord, Trade, WashSaleViolation
from net_alpha.web.app import create_app


def test_modal_renders_trades_and_adjustments(tmp_path):
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
        trade_count=2,
    )
    repo.add_import(
        acct,
        record,
        [
            Trade(account="Schwab/Tax", date=date(2026, 3, 1), ticker="AAPL",
                  action="Sell", quantity=10, proceeds=900.0, cost_basis=1000.0),
            Trade(account="Schwab/Tax", date=date(2026, 3, 15), ticker="AAPL",
                  action="Buy", quantity=10, cost_basis=950.0),
        ],
    )
    # Fetch DB-assigned trade IDs.
    all_trades = sorted(repo.all_trades(), key=lambda t: t.date)
    loss_trade = next(t for t in all_trades if t.action == "Sell")
    repl_trade = next(t for t in all_trades if t.action == "Buy")

    repo.replace_violations_in_window(
        date(2026, 1, 1), date(2027, 1, 1),
        [WashSaleViolation(
            loss_trade_id=loss_trade.id,
            replacement_trade_id=repl_trade.id,
            confidence="Confirmed",
            disallowed_loss=100.0,
            matched_quantity=10.0,
            loss_account="Schwab/Tax",
            buy_account="Schwab/Tax",
            loss_sale_date=date(2026, 3, 1),
            triggering_buy_date=date(2026, 3, 15),
            ticker="AAPL",
        )],
    )

    client = TestClient(create_app(settings))
    encoded = encode_metric_ref(WashImpactRef(
        kind="wash_impact",
        period=Period(start=date(2026, 1, 1), end=date(2027, 1, 1), label="YTD 2026"),
        account_id=acct.id,
    ))
    resp = client.get(f"/provenance/{encoded}")
    assert resp.status_code == 200
    assert "Confirmed" in resp.text
    assert "Pub 550" in resp.text
    assert "$100.00" in resp.text or "100.00" in resp.text
