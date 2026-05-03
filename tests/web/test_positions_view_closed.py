"""Route smoke for the Closed positions tab — replaces the Phase 2 placeholder.

Asserts /positions?view=closed renders real data (not the "Coming in Phase 2"
placeholder) when Realized G/L lots are present, and renders an actionable
empty state otherwise.
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.domain import ImportRecord
from net_alpha.models.realized_gl import RealizedGLLot
from net_alpha.web.app import create_app


def _seed(tmp_path, *, gl_lots: list[RealizedGLLot]) -> Settings:
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)
    acct = repo.get_or_create_account(broker="Schwab", label="Tax")
    record = ImportRecord(
        account_id=acct.id,
        csv_filename="gl.csv",
        csv_sha256="h",
        imported_at=datetime.now(),
        trade_count=0,
    )
    repo.add_import(acct, record, [])
    if gl_lots:
        repo.add_gl_lots(acct, import_id=1, lots=gl_lots)
    return settings


def test_closed_view_renders_real_table_with_gl_data(tmp_path):
    settings = _seed(
        tmp_path,
        gl_lots=[
            RealizedGLLot(
                account_display="Schwab/Tax",
                symbol_raw="AAPL",
                ticker="AAPL",
                closed_date=date.today().replace(month=1, day=15),
                opened_date=date.today().replace(year=date.today().year - 1, month=6, day=1),
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
    r = client.get("/positions?view=closed&period=ytd")
    assert r.status_code == 200
    body = r.text
    assert "Coming in Phase 2" not in body
    assert "AAPL" in body
    assert "$500.00" in body or "+$500.00" in body
    assert "1 closed lot" in body
    # LT chip visible (Long Term)
    assert ">LT<" in body


def test_closed_view_empty_state_when_no_gl_data(tmp_path):
    settings = _seed(tmp_path, gl_lots=[])
    client = TestClient(create_app(settings))
    r = client.get("/positions?view=closed&period=ytd")
    assert r.status_code == 200
    body = r.text
    assert "Coming in Phase 2" not in body
    assert "No closed positions" in body
    assert "Settings" in body  # empty-state pointer mentions Settings


def test_closed_view_period_filter_excludes_other_years(tmp_path):
    settings = _seed(
        tmp_path,
        gl_lots=[
            RealizedGLLot(
                account_display="Schwab/Tax",
                symbol_raw="AAPL",
                ticker="AAPL",
                closed_date=date(2024, 6, 1),
                opened_date=date(2024, 1, 1),
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
    # 2024 lot should NOT appear under year=2025
    r = client.get("/positions?view=closed&period=2025")
    assert r.status_code == 200
    assert "No closed positions" in r.text
    # but does appear under year=2024
    r = client.get("/positions?view=closed&period=2024")
    assert r.status_code == 200
    assert "AAPL" in r.text
    assert "1 closed lot" in r.text
    # and under lifetime
    r = client.get("/positions?view=closed&period=lifetime")
    assert r.status_code == 200
    assert "AAPL" in r.text


def test_closed_positions_header_shows_total_count_not_page_count(tmp_path):
    """When pagination kicks in (page_size < total rows), the header must
    show the total row count, not just the number of rows on the current page.
    """
    # Seed 3 GL lots but request page_size=2 — header must say "3 closed lots"
    # not "2 closed lots".
    gl_lots = [
        RealizedGLLot(
            account_display="Schwab/Tax",
            symbol_raw=sym,
            ticker=sym,
            closed_date=date(2025, 3, 1),
            opened_date=date(2025, 1, 1),
            quantity=1.0,
            proceeds=110.0,
            cost_basis=100.0,
            unadjusted_cost_basis=100.0,
            wash_sale=False,
            disallowed_loss=0.0,
            term="Short Term",
        )
        for sym in ["AAPL", "MSFT", "GOOG"]
    ]
    settings = _seed(tmp_path, gl_lots=gl_lots)
    client = TestClient(create_app(settings))
    r = client.get("/positions?view=closed&period=lifetime&page=1&page_size=2")
    assert r.status_code == 200
    # Header must reflect total (3), not page size (2).
    assert "3 closed lots" in r.text
