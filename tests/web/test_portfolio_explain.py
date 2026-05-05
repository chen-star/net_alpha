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


def test_explain_total_return_decomposition_total_has_label(tmp_path):
    """The Decomposition section's total row must carry the '= Total Return'
    label — otherwise the hairline rule + value hang in space with no label,
    which is a visible format bug.
    """
    client, _ = _make_client(tmp_path)
    r = client.get("/portfolio/explain/total-return?period=ytd")
    assert r.status_code == 200
    html = r.text
    assert "Decomposition:" in html
    # '= Total Return' must appear twice: once for the top equation total,
    # once for the decomposition total row.
    assert html.count("= Total Return") >= 2, (
        "Decomposition total row is missing its '= Total Return' label (empty <div> with a hairline rule)."
    )


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


def test_explain_total_return_caveat_when_starting_value_lots_unpriced(tmp_path):
    """When the starting-value computation silently drops unpriced lots, the
    explainer panel must surface a caveat — otherwise an undercounted
    starting value invisibly inflates Total Return and the user has no way
    to notice.
    """
    from datetime import date, datetime
    from decimal import Decimal

    from net_alpha.models.domain import CashEvent, ImportRecord, Trade

    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)

    # Seed: deposit + buy in 2025 of a ticker yfinance won't have in the test
    # cache → starting-value lookup for 12/31/2025 will silently drop the lot.
    acct = repo.get_or_create_account(broker="Schwab", label="Tax")
    record = ImportRecord(
        account_id=acct.id,
        csv_filename="t.csv",
        csv_sha256="x",
        imported_at=datetime.now(),
        trade_count=1,
    )
    trade = Trade(
        account="Schwab/Tax",
        date=date(2025, 6, 1),
        ticker="UNPRICED",
        action="Buy",
        quantity=Decimal("10"),
        proceeds=None,
        cost_basis=Decimal("500"),
    )
    cash_event = CashEvent(
        account="Schwab/Tax",
        event_date=date(2025, 1, 5),
        kind="deposit",
        amount=Decimal("1000"),
        description="seed",
    )
    repo.add_import(acct, record, [trade], cash_events=[cash_event])
    # add_import inserts only trade rows. Lots are materialized from buy
    # trades by the wash-sale recompute pass — without this call the lots
    # table stays empty and account_value_at sees nothing to drop.
    from net_alpha.engine.recompute import recompute_all_violations

    recompute_all_violations(repo, {})

    app = create_app(settings)
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/portfolio/explain/total-return?period=ytd")
    assert r.status_code == 200
    html = r.text
    assert "Starting value may be undercounted" in html, (
        "Explainer must show the unpriced-lots caveat when starting_value's "
        "_close_with_forward_fill returns None for any equity lot."
    )
    assert "UNPRICED" in html
    assert 'data-explain="starting-value-caveat"' in html


def test_explain_total_return_no_caveat_when_no_unpriced_lots(tmp_path):
    """The caveat banner must NOT appear on an empty/clean DB so it doesn't
    add chrome to the typical case."""
    client, _ = _make_client(tmp_path)
    r = client.get("/portfolio/explain/total-return?period=ytd")
    assert r.status_code == 200
    assert "Starting value may be undercounted" not in r.text
    assert 'data-explain="starting-value-caveat"' not in r.text


def test_explain_total_return_realized_scoped_by_account(tmp_path):
    """The Total Return decomposition's "Realized P/L (period)" must only sum
    GL realizations for the selected account.

    Regression: previously the route pre-filtered trades/lots by account but
    passed account=None plus all-account gl_lots into compute_kpis, which only
    filters gl_lots when its `account` arg is truthy. The result was that the
    decomposition's realized leg silently included other accounts' GL P&L,
    making the explainer disagree with the standalone Realized P/L tile.
    """
    from datetime import date, datetime

    from net_alpha.models.domain import ImportRecord
    from net_alpha.models.realized_gl import RealizedGLLot

    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)

    # Two accounts, each with a closed lot in YTD of the current year so the
    # default `?period=ytd` window catches them.
    today = date.today()
    closed_in_period = date(today.year, 1, 15)
    opened_prior = date(today.year - 1, 6, 1)
    acct_a = repo.get_or_create_account(broker="Schwab", label="A")
    acct_b = repo.get_or_create_account(broker="Schwab", label="B")
    rec_a = ImportRecord(
        account_id=acct_a.id,
        csv_filename="gl_a.csv",
        csv_sha256="aaa",
        imported_at=datetime.now(),
        trade_count=0,
    )
    rec_b = ImportRecord(
        account_id=acct_b.id,
        csv_filename="gl_b.csv",
        csv_sha256="bbb",
        imported_at=datetime.now(),
        trade_count=0,
    )
    repo.add_import(acct_a, rec_a, [])
    repo.add_import(acct_b, rec_b, [])
    repo.add_gl_lots(
        acct_a,
        import_id=1,
        lots=[
            RealizedGLLot(
                account_display="Schwab/A",
                symbol_raw="AAA",
                ticker="AAA",
                closed_date=closed_in_period,
                opened_date=opened_prior,
                quantity=10.0,
                proceeds=1100.0,
                cost_basis=1000.0,  # +100 realized
                unadjusted_cost_basis=1000.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Long Term",
            )
        ],
    )
    repo.add_gl_lots(
        acct_b,
        import_id=2,
        lots=[
            RealizedGLLot(
                account_display="Schwab/B",
                symbol_raw="BBB",
                ticker="BBB",
                closed_date=closed_in_period,
                opened_date=opened_prior,
                quantity=10.0,
                proceeds=1500.0,
                cost_basis=1000.0,  # +500 realized — must NOT leak into A
                unadjusted_cost_basis=1000.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Long Term",
            )
        ],
    )

    app = create_app(settings)
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/portfolio/explain/total-return?period=ytd&account=Schwab%2FA")
    assert r.status_code == 200
    html = r.text
    # Realized P/L (period) row should show A's $100, not the cross-account $600.
    assert "Realized P/L (period)" in html
    assert "+$100.00" in html, (
        "Decomposition's Realized P/L (period) should equal account A's $100.00, "
        "but it isn't present in the rendered fragment."
    )
    assert "+$600.00" not in html, (
        "Decomposition's Realized P/L (period) leaked account B's GL — "
        "rendered as the cross-account $600.00 sum instead of A's $100.00."
    )


def test_explain_account_value_smoke_empty_db(tmp_path):
    """explain_account_value returns 200 on an empty database (no crash)."""
    client, _ = _make_client(tmp_path)
    r = client.get("/portfolio/explain/account-value")
    assert r.status_code == 200


def test_explain_account_value_smoke_with_account_filter(tmp_path):
    """explain_account_value accepts an account query param without crashing."""
    client, _ = _make_client(tmp_path)
    r = client.get("/portfolio/explain/account-value?account=Schwab%2FTax")
    assert r.status_code == 200


def test_explain_account_value_renders_both_equation_headings(tmp_path):
    """Both equation sections must render labeled subtotal rows so the
    panel is readable on an empty DB (no positions, no contributions).
    """
    client, _ = _make_client(tmp_path)
    r = client.get("/portfolio/explain/account-value")
    assert r.status_code == 200
    html = r.text
    # Composition equation rows
    assert "Cash balance" in html
    assert "Long stock" in html  # tolerate "Long stock & ETF market value"
    assert "Long option" in html
    assert "Short option" in html
    # Source equation rows
    assert "Net contributed" in html
    assert "Lifetime realized P/L" in html
    assert "Current unrealized P/L" in html
    # Both equations must show a labeled "= Total Account Value" total row
    assert html.count("= Total Account Value") >= 2, (
        "Both Composition and Source totals must carry the '= Total Account Value' "
        "label or the hairline rule + value hangs in space with no label."
    )
    # Standard disclaimer
    assert "Consult a tax professional" in html


def test_portfolio_kpis_renders_account_value_explain_trigger(tmp_path):
    """The hero KPI tile must include the info-circle button wired to
    /portfolio/explain/account-value and a mount div for the fragment.
    """
    client, _ = _make_client(tmp_path)
    r = client.get("/portfolio/kpis")
    assert r.status_code == 200
    html = r.text
    assert 'hx-get="/portfolio/explain/account-value' in html, (
        "Hero tile is missing the info-circle button that opens the Account Value explainer."
    )
    assert 'id="explain-account-value"' in html, (
        "Hero tile is missing the <div id='explain-account-value'> mount point for the fragment."
    )


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
