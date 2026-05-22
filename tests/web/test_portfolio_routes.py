from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import text

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine
from net_alpha.web.app import create_app


def _client(tmp_path):
    return TestClient(create_app(Settings(data_dir=tmp_path)))


def test_root_renders_portfolio_when_no_imports(tmp_path):
    client = _client(tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    assert "Portfolio" in response.text
    # New empty-state hero (Tasks 8/9): "No portfolio yet" plus tour + import CTAs.
    assert "No portfolio yet" in response.text
    assert "Take a 30s tour" in response.text
    assert "Import CSV" in response.text


def test_root_renders_portfolio_toolbar_when_imports_exist(tmp_path):
    client = _client(tmp_path)
    # Quick way to exercise the "with imports" path: insert one stub import.
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO accounts(broker, label) VALUES ('Schwab', 'Tax')"))
        conn.execute(
            text(
                "INSERT INTO imports(account_id, csv_filename, csv_sha256, imported_at, trade_count) "
                "VALUES (1, 'x.csv', 'h', '2026-04-26T00:00:00', 0)"
            )
        )
    response = client.get("/")
    assert response.status_code == 200
    assert "Period:" in response.text  # toolbar present
    assert "Account:" in response.text


def test_kpis_fragment_renders_with_no_data(tmp_path):
    client = _client(tmp_path)
    response = client.get("/portfolio/kpis?period=ytd")
    assert response.status_code == 200
    assert "Realized" in response.text
    assert "Unrealized" in response.text


def test_positions_fragment_empty_state(tmp_path):
    client = _client(tmp_path)
    response = client.get("/portfolio/positions?period=ytd")
    assert response.status_code == 200
    assert "No open positions" in response.text


def test_equity_curve_fragment_no_data(tmp_path):
    client = _client(tmp_path)
    r = client.get("/portfolio/equity-curve?period=ytd")
    assert r.status_code == 200
    assert "Equity curve" in r.text


def test_portfolio_body_fragment_returns_overview_panels(tmp_path):
    """The bundled body fragment renders KPIs + equity-curve + allocation."""
    client = _client(tmp_path)
    response = client.get("/portfolio/body?period=ytd&account=")
    assert response.status_code == 200
    html = response.text
    # KPIs panel marker (label appears in _portfolio_kpis.html).
    assert "Realized" in html
    assert "Unrealized" in html
    # Equity curve panel.
    assert "Equity curve" in html
    # Allocation row contains both the concentration donut AND the
    # cash-vs-positions deployment chart, side by side.
    assert 'id="portfolio-allocation"' in html
    assert 'id="portfolio-deployment"' in html
    # Wash-sale watch lives on /tax now — must NOT be in the portfolio body.
    assert "Wash-sale watch" not in html
    assert 'id="portfolio-wash-watch"' not in html
    # Wash impact KPI tile is also gone.
    assert 'data-kpi-slot="wash_impact"' not in html
    # Positions table is NOT in the body — it lives on /holdings.
    assert "No open positions" not in html
    assert 'id="portfolio-positions"' not in html


def test_portfolio_page_uses_single_bundled_fragment(tmp_path):
    """The /portfolio shell should issue ONE hx-get to /portfolio/body, not five."""
    client = _client(tmp_path)
    # Quick way to exercise the "with imports" path: insert one stub import.
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO accounts(broker, label) VALUES ('Schwab', 'Tax')"))
        conn.execute(
            text(
                "INSERT INTO imports(account_id, csv_filename, csv_sha256, imported_at, trade_count) "
                "VALUES (1, 'x.csv', 'h', '2026-04-26T00:00:00', 0)"
            )
        )
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "/portfolio/body" in html
    # The old per-panel page-load triggers should be gone from the shell.
    assert html.count('hx-get="/portfolio/kpis') == 0
    assert html.count('hx-get="/portfolio/equity-curve') == 0
    assert html.count('hx-get="/portfolio/allocation') == 0
    assert html.count('hx-get="/portfolio/wash-watch') == 0
    assert html.count('hx-get="/portfolio/positions') == 0


def test_positions_symbols_filter(tmp_path):
    """?symbols=AAPL,MSFT keeps only those tickers (case-insensitive)."""
    client = _client(tmp_path)
    # No data yet — empty list returns. We just check the param is accepted
    # and returns 200; behavior with data is covered in detail tests.
    r = client.get("/portfolio/positions?period=ytd&symbols=aapl,MSFT")
    assert r.status_code == 200


def test_positions_no_q_param(tmp_path):
    """The legacy q substring filter must be gone (replaced by symbols)."""
    client = _client(tmp_path)
    r = client.get("/portfolio/positions?period=ytd")
    assert r.status_code == 200
    # The toolbar markup should NOT include a search input named 'q'.
    assert 'name="q"' not in r.text
    # And the route should not interpolate {{ search_q }} anywhere.
    assert "search_q" not in r.text.lower()


def test_equity_curve_fragment_template_uses_new_series(tmp_path):
    """Empty-state path still renders the panel; old series name is removed
    from the codebase. The data-driven 'series defined' assertion lives in
    the browser smoke test (Task 8) since seeding a fully-priced portfolio
    via raw SQL here would be brittle."""
    client = _client(tmp_path)
    r = client.get("/portfolio/equity-curve?period=ytd")
    assert r.status_code == 200
    assert "Equity curve" in r.text
    # The old broken series name from _portfolio_equity_curve.html must be gone.
    assert "Total (incl. unrealized)" not in r.text


def test_portfolio_body_renders_monthly_pl_panel_ytd(tmp_path):
    """The monthly realized-P/L panel renders inside /portfolio/body for YTD
    even with no trades (empty-state copy must appear)."""
    client = _client(tmp_path)
    response = client.get("/portfolio/body?period=ytd&account=")
    assert response.status_code == 200
    html = response.text
    # Panel chrome must be present.
    assert 'id="portfolio-monthly-pl"' in html
    assert "Monthly realized P&amp;L" in html or "Monthly realized P&L" in html
    # No imports yet -> no realized closes in YTD -> empty-state copy.
    assert "No realized closes in" in html


def test_portfolio_body_renders_monthly_pl_panel_specific_year(tmp_path):
    """Specific-year scope still emits the panel + its empty state.

    With no trades anywhere, the spec says a no-Sells-in-period scope hits
    the empty-state branch (`has_data` = sum(trade_count) > 0). We pin both
    halves of that contract: the period label appears in the panel head AND
    the empty-state copy is what fills the chart area (not zero bars).
    """
    client = _client(tmp_path)
    response = client.get("/portfolio/body?period=2025&account=")
    assert response.status_code == 200
    html = response.text
    assert 'id="portfolio-monthly-pl"' in html
    assert "No realized closes in 2025" in html


def test_portfolio_body_renders_monthly_pl_panel_lifetime(tmp_path):
    """Lifetime scope renders the panel; with no trades the empty state
    appears (Lifetime returns []  -> has_data is false)."""
    client = _client(tmp_path)
    response = client.get("/portfolio/body?period=lifetime&account=")
    assert response.status_code == 200
    html = response.text
    assert 'id="portfolio-monthly-pl"' in html
    assert "Lifetime" in html
    assert "No realized closes in" in html


def test_cash_curve_renders_lifetime_minmax_on_period(tmp_path):
    """Cash curve renders lifetime min/max in the panel-head on period-scoped
    views. The old "Lifetime min … (date)" footnote line below the chart was
    replaced with an inline min/max chip in the panel-head ("min $X mon 'yy
    · max $Y mon 'yy") — same information, but pulled up where the rest of
    the chart's KPI summary lives."""
    from datetime import date, datetime

    from net_alpha.config import Settings
    from net_alpha.db.connection import get_engine, init_db
    from net_alpha.db.repository import Repository
    from net_alpha.models.domain import CashEvent, ImportRecord, Trade

    # Initialize DB and add test data (a buy trade generates cash data).
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)

    # Add a simple buy trade to generate cash history.
    account = repo.get_or_create_account("Schwab", "Test")
    trade = Trade(
        account="Schwab/Test",
        date=date(2026, 1, 15),
        ticker="AAPL",
        action="Buy",
        quantity=10.0,
        proceeds=None,
        cost_basis=18000.0,
    )
    record = ImportRecord(
        account_id=account.id,
        csv_filename="test.csv",
        csv_sha256="test",
        imported_at=datetime.now(),
        trade_count=1,
    )
    # add_import requires cash_events for the lifetime min/max KPI to be non-None
    cash_events = [CashEvent(account="Schwab/Test", event_date=date(2026, 1, 15), kind="transfer_in", amount=18000.0)]
    repo.add_import(account, record, [trade], cash_events=cash_events)

    # Now test the fragment with period=ytd.
    client = _client(tmp_path)
    r = client.get("/portfolio/body?period=ytd&account=")
    assert r.status_code == 200
    assert "min $" in r.text
    assert "· max $" in r.text


def test_cash_curve_omits_lifetime_minmax_on_lifetime_view(tmp_path):
    """Cash curve lifetime min/max chip is omitted when viewing Lifetime scope
    (the chart's domain already IS the lifetime, so a separate min/max is
    redundant)."""
    from datetime import date, datetime

    from net_alpha.config import Settings
    from net_alpha.db.connection import get_engine, init_db
    from net_alpha.db.repository import Repository
    from net_alpha.models.domain import CashEvent, ImportRecord, Trade

    # Initialize DB and add test data.
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)

    # Add a simple buy trade to generate cash history.
    account = repo.get_or_create_account("Schwab", "Test")
    trade = Trade(
        account="Schwab/Test",
        date=date(2026, 1, 15),
        ticker="AAPL",
        action="Buy",
        quantity=10.0,
        proceeds=None,
        cost_basis=18000.0,
    )
    record = ImportRecord(
        account_id=account.id,
        csv_filename="test.csv",
        csv_sha256="test",
        imported_at=datetime.now(),
        trade_count=1,
    )
    cash_events = [CashEvent(account="Schwab/Test", event_date=date(2026, 1, 15), kind="transfer_in", amount=18000.0)]
    repo.add_import(account, record, [trade], cash_events=cash_events)

    # Lifetime view should NOT include the min/max chip.
    client = _client(tmp_path)
    r = client.get("/portfolio/body?period=lifetime&account=")
    assert r.status_code == 200
    # The panel-head min/max chip uses literal "min $...· max $..." — assert
    # neither half is present on the lifetime view.
    assert "· max $" not in r.text


def test_monthly_pl_renders_lifetime_footnote_on_period(tmp_path):
    """Monthly P/L renders lifetime avg/best/worst footnote only on period-scoped views."""
    from datetime import date, datetime

    from net_alpha.config import Settings
    from net_alpha.db.connection import get_engine, init_db
    from net_alpha.db.repository import Repository
    from net_alpha.models.domain import ImportRecord, Trade

    # Initialize DB and add test data with a Buy + Sell to generate realized P&L.
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)

    # Add a buy and sell trade to generate monthly P&L history.
    account = repo.get_or_create_account("Schwab", "Test")
    trades = [
        Trade(
            account="Schwab/Test",
            date=date(2026, 1, 15),
            ticker="AAPL",
            action="Buy",
            quantity=10.0,
            proceeds=None,
            cost_basis=18000.0,
        ),
        Trade(
            account="Schwab/Test",
            date=date(2026, 2, 15),
            ticker="AAPL",
            action="Sell",
            quantity=10.0,
            proceeds=20000.0,
            cost_basis=18000.0,
        ),
    ]
    record = ImportRecord(
        account_id=account.id,
        csv_filename="test.csv",
        csv_sha256="test",
        imported_at=datetime.now(),
        trade_count=2,
    )
    repo.add_import(account, record, trades, cash_events=[])

    # Test with period=ytd — should include the lifetime footnote.
    client = _client(tmp_path)
    r = client.get("/portfolio/body?period=ytd&account=")
    assert r.status_code == 200
    assert "Lifetime avg $" in r.text
    assert "/mo" in r.text


def test_monthly_pl_omits_lifetime_footnote_on_lifetime_view(tmp_path):
    """Monthly P/L footnote is omitted when viewing Lifetime scope."""
    from datetime import date, datetime

    from net_alpha.config import Settings
    from net_alpha.db.connection import get_engine, init_db
    from net_alpha.db.repository import Repository
    from net_alpha.models.domain import ImportRecord, Trade

    # Initialize DB and add test data with a Buy + Sell.
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)

    # Add a buy and sell trade.
    account = repo.get_or_create_account("Schwab", "Test")
    trades = [
        Trade(
            account="Schwab/Test",
            date=date(2026, 1, 15),
            ticker="AAPL",
            action="Buy",
            quantity=10.0,
            proceeds=None,
            cost_basis=18000.0,
        ),
        Trade(
            account="Schwab/Test",
            date=date(2026, 2, 15),
            ticker="AAPL",
            action="Sell",
            quantity=10.0,
            proceeds=20000.0,
            cost_basis=18000.0,
        ),
    ]
    record = ImportRecord(
        account_id=account.id,
        csv_filename="test.csv",
        csv_sha256="test",
        imported_at=datetime.now(),
        trade_count=2,
    )
    repo.add_import(account, record, trades, cash_events=[])

    # Lifetime view should NOT include the footnote.
    client = _client(tmp_path)
    r = client.get("/portfolio/body?period=lifetime&account=")
    assert r.status_code == 200
    assert "Lifetime avg $" not in r.text


def test_kpi_tiles_show_lifetime_subtitle_on_period(tmp_path):
    """KPI tiles show Lifetime subtitles on period-scoped views."""
    from datetime import date, datetime

    from net_alpha.config import Settings
    from net_alpha.db.connection import get_engine, init_db
    from net_alpha.db.repository import Repository
    from net_alpha.models.domain import ImportRecord, Trade

    # Initialize DB and add test data with a Buy + Sell to generate realized P&L.
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)

    # Add a buy and sell trade to generate realized P&L.
    account = repo.get_or_create_account("Schwab", "Test")
    trades = [
        Trade(
            account="Schwab/Test",
            date=date(2026, 1, 15),
            ticker="AAPL",
            action="Buy",
            quantity=10.0,
            proceeds=None,
            cost_basis=18000.0,
        ),
        Trade(
            account="Schwab/Test",
            date=date(2026, 2, 15),
            ticker="AAPL",
            action="Sell",
            quantity=10.0,
            proceeds=20000.0,
            cost_basis=18000.0,
        ),
    ]
    record = ImportRecord(
        account_id=account.id,
        csv_filename="test.csv",
        csv_sha256="test",
        imported_at=datetime.now(),
        trade_count=2,
    )
    repo.add_import(account, record, trades, cash_events=[])

    # Test with period=ytd — should include the lifetime subtitles.
    client = _client(tmp_path)
    r = client.get("/portfolio/body?period=ytd&account=")
    assert r.status_code == 200
    # Tooltips uniquely identify our two new subtitles.
    assert "Account value today minus lifetime net contributed" in r.text
    # The Realized P/L Lifetime subtext was retitled to point users at the
    # value they see when switching Period to Lifetime — covered by the
    # tooltip on that subtitle.
    assert "matches the value shown when you switch Period to Lifetime" in r.text


def test_kpi_tiles_hide_lifetime_subtitle_on_lifetime_view(tmp_path):
    """KPI tiles hide Lifetime subtitles when viewing Lifetime scope."""
    from datetime import date, datetime

    from net_alpha.config import Settings
    from net_alpha.db.connection import get_engine, init_db
    from net_alpha.db.repository import Repository
    from net_alpha.models.domain import ImportRecord, Trade

    # Initialize DB and add test data with a Buy + Sell to generate realized P&L.
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)

    # Add a buy and sell trade to generate realized P&L.
    account = repo.get_or_create_account("Schwab", "Test")
    trades = [
        Trade(
            account="Schwab/Test",
            date=date(2026, 1, 15),
            ticker="AAPL",
            action="Buy",
            quantity=10.0,
            proceeds=None,
            cost_basis=18000.0,
        ),
        Trade(
            account="Schwab/Test",
            date=date(2026, 2, 15),
            ticker="AAPL",
            action="Sell",
            quantity=10.0,
            proceeds=20000.0,
            cost_basis=18000.0,
        ),
    ]
    record = ImportRecord(
        account_id=account.id,
        csv_filename="test.csv",
        csv_sha256="test",
        imported_at=datetime.now(),
        trade_count=2,
    )
    repo.add_import(account, record, trades, cash_events=[])

    # Lifetime view should NOT include the lifetime subtitles.
    client = _client(tmp_path)
    r = client.get("/portfolio/body?period=lifetime&account=")
    assert r.status_code == 200
    assert "Account value today minus lifetime net contributed" not in r.text
    assert "matches the value shown when you switch Period to Lifetime" not in r.text


def _setup_trade_data(tmp_path):
    """Insert a buy trade + cash event so lifetime_account_points is non-empty."""
    from datetime import date, datetime

    from net_alpha.config import Settings
    from net_alpha.db.connection import get_engine, init_db
    from net_alpha.db.repository import Repository
    from net_alpha.models.domain import CashEvent, ImportRecord, Trade

    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)

    account = repo.get_or_create_account("Schwab", "Test")
    trade = Trade(
        account="Schwab/Test",
        date=date(2026, 1, 15),
        ticker="AAPL",
        action="Buy",
        quantity=10.0,
        proceeds=None,
        cost_basis=18000.0,
    )
    record = ImportRecord(
        account_id=account.id,
        csv_filename="test.csv",
        csv_sha256="brush_test",
        imported_at=datetime.now(),
        trade_count=1,
    )
    cash_events = [
        CashEvent(
            account="Schwab/Test",
            event_date=date(2026, 1, 15),
            kind="transfer_in",
            amount=18000.0,
        )
    ]
    repo.add_import(account, record, [trade], cash_events=cash_events)


def test_equity_curve_omits_brush_strip(tmp_path):
    """The lifetime brush strip was removed — the Period dropdown handles the
    same re-period intent more clearly, and the strip's lifetime account-value
    compute dominated cold body-load latency. The body must no longer ship
    any brush DOM nodes or hit the /portfolio/equity-curve/brush endpoint."""
    _setup_trade_data(tmp_path)
    client = _client(tmp_path)
    for period in ("ytd", "lifetime"):
        r = client.get(f"/portfolio/body?period={period}")
        assert r.status_code == 200, period
        assert 'id="equity-brush-slot"' not in r.text, period
        assert 'id="equity-chart-lifetime"' not in r.text, period
        assert "/portfolio/equity-curve/brush" not in r.text, period
    # The endpoint itself is gone too.
    assert client.get("/portfolio/equity-curve/brush?period=ytd").status_code == 404


def test_portfolio_body_includes_month_end_context(tmp_path):
    """The body context exposes the month-end equity series + summary + year picker flag.

    UI rendering of the new panel is Task 6 — here we only verify the route
    handler doesn't blow up and the body still returns 200 for all three
    period modes (ytd, specific year, lifetime).
    """
    client = _client(tmp_path)
    for period in ("ytd", "2025", "lifetime"):
        response = client.get(f"/portfolio/body?period={period}&account=")
        assert response.status_code == 200, f"period={period!r} returned {response.status_code}"
