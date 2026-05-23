from datetime import date, datetime

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.domain import ImportRecord, Trade
from net_alpha.models.realized_gl import RealizedGLLot
from net_alpha.web.app import create_app


def _seed_clean(tmp_path):
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
        ],
    )
    return acct, settings


def test_reconciliation_route_returns_match_strip(tmp_path):
    acct, settings = _seed_clean(tmp_path)
    repo = Repository(get_engine(settings.db_path))
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
    resp = client.get(f"/reconciliation/AAPL?account_id={acct.id}")
    assert resp.status_code == 200
    assert "✓" in resp.text or "match" in resp.text.lower()
    assert "$500.00" in resp.text or "500.00" in resp.text


def test_reconciliation_route_renders_diff_state(tmp_path):
    acct, settings = _seed_clean(tmp_path)
    repo = Repository(get_engine(settings.db_path))
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
                proceeds=1495.00,
                cost_basis=1000.0,
                unadjusted_cost_basis=1000.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Long Term",
            )
        ],
    )
    client = TestClient(create_app(settings))
    resp = client.get(f"/reconciliation/AAPL?account_id={acct.id}")
    assert resp.status_code == 200
    assert "△" in resp.text or "investigate" in resp.text.lower()


def test_reconciliation_route_period_scope_narrows_to_year(tmp_path):
    """Audit #15 follow-up: ``?period=<YYYY>`` must narrow net-alpha's
    side to that year so a multi-year ledger reconciled against a
    single-year broker file yields MATCH instead of a spurious DIFF.
    """
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
            # 2024 — NOT in the broker file below.
            Trade(
                account="Schwab/Tax", date=date(2024, 1, 5), ticker="AAPL",
                action="Buy", quantity=10, cost_basis=1000.0,
            ),
            Trade(
                account="Schwab/Tax", date=date(2024, 6, 1), ticker="AAPL",
                action="Sell", quantity=10, proceeds=1100.0, cost_basis=1000.0,
            ),
            # 2025 — covered by the broker file.
            Trade(
                account="Schwab/Tax", date=date(2025, 1, 5), ticker="AAPL",
                action="Buy", quantity=10, cost_basis=1200.0,
            ),
            Trade(
                account="Schwab/Tax", date=date(2025, 4, 1), ticker="AAPL",
                action="Sell", quantity=10, proceeds=1500.0, cost_basis=1200.0,
            ),
        ],
    )
    repo.add_gl_lots(
        acct,
        import_id=1,
        lots=[
            RealizedGLLot(
                account_display="Schwab/Tax", symbol_raw="AAPL", ticker="AAPL",
                closed_date=date(2025, 4, 1), opened_date=date(2025, 1, 5),
                quantity=10.0, proceeds=1500.0, cost_basis=1200.0,
                unadjusted_cost_basis=1200.0, wash_sale=False, disallowed_loss=0.0,
                term="Short Term",
            ),
        ],
    )
    client = TestClient(create_app(settings))

    # Without period scope, the engine sums all years on the net-alpha
    # side ($400) vs the 2025-only broker side ($300) — DIFF.
    lifetime = client.get(f"/reconciliation/AAPL?account_id={acct.id}&variant=badge")
    assert lifetime.status_code == 200
    assert "△" in lifetime.text or "investigate" in lifetime.text.lower()

    # With period=2025, both sides narrow to $300 — MATCH.
    scoped = client.get(f"/reconciliation/AAPL?account_id={acct.id}&variant=badge&period=2025")
    assert scoped.status_code == 200
    assert "✓" in scoped.text or "match" in scoped.text.lower()
