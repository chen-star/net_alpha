"""Tests for the GET /sim/suggestions chip-strip endpoint."""

import pathlib
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.web.app import create_app


def _client():
    d = tempfile.mkdtemp()
    s = Settings(data_dir=pathlib.Path(d))
    app = create_app(s)
    return TestClient(app)


def test_endpoint_returns_at_least_one_chip():
    """On a fresh empty DB, the demo-fallback chip should render with a valid /sim href."""
    with _client() as c:
        r = c.get("/sim/suggestions")
    assert r.status_code == 200
    assert "/sim?" in r.text


def test_chips_strip_loaded_lazily_on_sim_page():
    """The Sim form page emits a placeholder div that lazy-loads /sim/suggestions."""
    with _client() as c:
        r = c.get("/sim")
    assert r.status_code == 200
    html = r.text
    assert 'hx-get="/sim/suggestions"' in html or "hx-get='/sim/suggestions'" in html


def test_demo_chip_uses_safe_action():
    """Demo chip should propose a sell of TSLA 10 @ 180 with action=sell."""
    with _client() as c:
        r = c.get("/sim/suggestions")
    html = r.text
    assert "ticker=TSLA" in html
    assert "action=sell" in html


# ---------------------------------------------------------------------------
# Task 5.1 — WOLF bug: fully-closed positions must not appear in chips
# ---------------------------------------------------------------------------


def test_fully_closed_position_does_not_appear_in_chips(repo, client):
    """Reproduces the WOLF bug: a position that's been fully sold via FIFO
    must not appear in sim suggestions chips.

    Uses a stub PricingService that returns synthetic quotes so the positions
    engine has market values to work with. The closed WOLF position must be
    excluded; the still-open SQQQ position must be included.
    """
    from net_alpha.engine.detector import detect_in_window
    from net_alpha.models.domain import Trade
    from net_alpha.pricing.provider import Quote
    from net_alpha.pricing.service import PricingService
    from net_alpha.web.routes.sim import _build_sim_positions

    _NOW = datetime.now(tz=timezone.utc)

    # Seed: WOLF fully bought then fully sold; SQQQ still open.
    account = repo.get_or_create_account("Schwab", "X")
    account_display = account.display()

    trades = [
        Trade(
            account=account_display,
            date=date(2026, 2, 1),
            ticker="WOLF",
            action="Buy",
            quantity=100.0,
            cost_basis=500.0,
            proceeds=None,
        ),
        Trade(
            account=account_display,
            date=date(2026, 3, 1),
            ticker="WOLF",
            action="Sell",
            quantity=100.0,
            cost_basis=500.0,
            proceeds=400.0,
        ),
        Trade(
            account=account_display,
            date=date(2026, 1, 15),
            ticker="SQQQ",
            action="Buy",
            quantity=50.0,
            cost_basis=2500.0,
            proceeds=None,
        ),
    ]

    from net_alpha.models.domain import ImportRecord

    record = ImportRecord(
        account_id=account.id,
        csv_filename="wolf_test.csv",
        csv_sha256="sha-wolf-test",
        imported_at=datetime.now(),
        trade_count=len(trades),
    )
    repo.add_import(account, record, trades)

    # Populate lots via the engine (same pattern as test_tax_route.py)
    all_trades = repo.all_trades()
    min_date = min(t.date for t in all_trades)
    max_date = max(t.date for t in all_trades)
    result = detect_in_window(all_trades, min_date, max_date, etf_pairs={})
    repo.replace_lots_in_window(min_date, max_date, result.lots)

    # Stub pricing: give both symbols a price so the filter on market_value
    # won't hide SQQQ. WOLF must still be excluded because FIFO consumed it.
    class _StubPricing:
        def get_prices(self, symbols):
            return {
                sym: Quote(
                    symbol=sym,
                    price=Decimal("10.00"),
                    as_of=_NOW,
                    source="stub",
                )
                for sym in symbols
            }

    positions = _build_sim_positions(repo=repo, pricing=_StubPricing())

    symbols_in_positions = {p.symbol for p in positions}
    assert "WOLF" not in symbols_in_positions, "fully-closed WOLF must not appear in sim positions"
    assert "SQQQ" in symbols_in_positions, "open SQQQ must appear in sim positions"
