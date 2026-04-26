"""End-to-end: import a fixture CSV, hit Portfolio page, verify all fragments load."""

import datetime as dt
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import text

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine
from net_alpha.pricing.provider import Quote
from net_alpha.web.app import create_app


def test_portfolio_page_full_render(tmp_path):
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings)
    client = TestClient(app)

    # Patch the provider so no network is needed.
    fake = {
        "SPY": Quote(symbol="SPY", price=Decimal("460.5"),
                     as_of=dt.datetime.now(dt.UTC), source="yahoo"),
    }
    with patch.object(app.state.price_provider, "get_quotes", return_value=fake):
        # Empty state: page renders with CTA.
        r = client.get("/")
        assert r.status_code == 200
        assert "No imports yet" in r.text

        # Insert a stub trade + lot directly to exercise the populated path.
        engine = get_engine(settings.db_path)
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO accounts(broker, label) VALUES ('Schwab', 'Tax')"))
            conn.execute(text(
                "INSERT INTO imports(account_id, csv_filename, csv_sha256, imported_at, trade_count) "
                "VALUES (1, 'x.csv', 'h', '2026-04-26T00:00:00', 1)"
            ))
            conn.execute(text(
                "INSERT INTO trades(import_id, account_id, natural_key, ticker, trade_date, action, "
                "quantity, proceeds, cost_basis, basis_unknown, basis_source) "
                "VALUES (1, 1, 'k1', 'SPY', '2025-01-15', 'Buy', 100, NULL, 40000, 0, 'broker_csv')"
            ))
            conn.execute(text(
                "INSERT INTO lots(trade_id, account_id, ticker, trade_date, quantity, cost_basis, adjusted_basis) "
                "VALUES (1, 1, 'SPY', '2025-01-15', 100, 40000, 40000)"
            ))

        # Page now shows toolbar.
        r = client.get("/")
        assert r.status_code == 200
        assert "Period:" in r.text

        # All fragments respond 200 with content.
        for path in [
            "/portfolio/kpis?period=ytd",
            "/portfolio/positions?period=ytd",
            "/portfolio/treemap",
            "/portfolio/equity-curve?period=ytd",
            "/portfolio/wash-impact?period=ytd",
            "/portfolio/lot-aging",
        ]:
            r = client.get(path)
            assert r.status_code == 200, f"{path} returned {r.status_code}"
            assert len(r.text.strip()) > 0
