"""Tests for the portfolio explain endpoints (Total Return + Unrealized P/L)."""

from __future__ import annotations

import pathlib

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.web.app import create_app


def _make_client(tmp_path: pathlib.Path) -> tuple[TestClient, Repository]:
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)
    app = create_app(settings)
    client = TestClient(app, raise_server_exceptions=False)
    return client, repo


def test_explain_unrealized_smoke_empty_db(tmp_path):
    """explain_unrealized returns 200 on an empty database (no crash)."""
    client, _ = _make_client(tmp_path)
    r = client.get("/portfolio/explain/unrealized")
    assert r.status_code == 200


def test_explain_unrealized_smoke_with_account_filter(tmp_path):
    """explain_unrealized accepts an account query param without crashing."""
    client, _ = _make_client(tmp_path)
    r = client.get("/portfolio/explain/unrealized?account=Schwab%2FTax")
    assert r.status_code == 200


def test_explain_unrealized_gl_closure_wired(tmp_path):
    """When a lot is fully closed by a Realized G/L import (no Sell trade),
    the explainer endpoint must not crash and must return 200, confirming
    GL closures are threaded through consume_lots_fifo correctly.
    """
    from datetime import date, datetime
    from decimal import Decimal

    from net_alpha.models.domain import ImportRecord, Trade
    from net_alpha.models.realized_gl import RealizedGLLot

    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)

    # Seed account + buy trade + GL closure (no matching Sell trade).
    acct = repo.get_or_create_account(broker="Schwab", label="Tax")
    buy_trade = Trade(
        account="Schwab/Tax",
        date=date(2025, 1, 10),
        ticker="AAPL",
        action="Buy",
        quantity=Decimal("10"),
        proceeds=None,
        cost_basis=Decimal("1500"),
    )
    record = ImportRecord(
        account_id=acct.id,
        csv_filename="trades.csv",
        csv_sha256="abc123",
        imported_at=datetime.now(),
        trade_count=1,
    )
    repo.add_import(acct, record, [buy_trade])

    # Add a GL closure simulating Schwab reported the close in Realized G/L CSV.
    gl_lot = RealizedGLLot(
        account_display="Schwab/Tax",
        symbol_raw="AAPL",
        ticker="AAPL",
        closed_date=date(2025, 6, 1),
        opened_date=date(2025, 1, 10),
        quantity=10.0,
        proceeds=1800.0,
        cost_basis=1500.0,
        unadjusted_cost_basis=1500.0,
        wash_sale=False,
        disallowed_loss=0.0,
        term="Long Term",
    )
    record2 = ImportRecord(
        account_id=acct.id,
        csv_filename="gl.csv",
        csv_sha256="def456",
        imported_at=datetime.now(),
        trade_count=0,
    )
    repo.add_import(acct, record2, [])
    repo.add_gl_lots(acct, import_id=2, lots=[gl_lot])

    app = create_app(settings)
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/portfolio/explain/unrealized")
    # Must not 500 — GL closures are now correctly passed to consume_lots_fifo.
    assert r.status_code == 200
