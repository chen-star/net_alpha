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
    assert "Import your first CSV" in response.text


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
