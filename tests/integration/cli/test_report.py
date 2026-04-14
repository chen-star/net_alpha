"""CLI integration tests: net-alpha report command."""
from __future__ import annotations

import csv
from datetime import date
from uuid import uuid4

import pytest
from sqlmodel import Session

from net_alpha.cli.app import app
from net_alpha.db.repository import TradeRepository
from net_alpha.models.domain import Trade

DISCLAIMER = "Consult a tax professional"


def _seed_wash_sale(engine, ticker: str, year: int, loss: float = 1000.0):
    """Seed a loss sale + replacement buy. Engine will detect as Confirmed."""
    with Session(engine) as s:
        TradeRepository(s).save_batch([
            Trade(
                id=str(uuid4()), account="Schwab",
                date=date(year, 6, 1), ticker=ticker,
                action="Sell", quantity=10.0,
                proceeds=2000.0, cost_basis=2000.0 + loss,
            ),
            Trade(
                id=str(uuid4()), account="Schwab",
                date=date(year, 6, 10), ticker=ticker,
                action="Buy", quantity=10.0, cost_basis=2200.0,
            ),
        ])
        s.commit()


def test_report_summary(cli_setup):
    """3 wash sale pairs in 2024: counts and total disallowed shown."""
    runner, engine, _ = cli_setup
    _seed_wash_sale(engine, "TSLA", 2024, loss=1000.0)
    _seed_wash_sale(engine, "AAPL", 2024, loss=500.0)
    _seed_wash_sale(engine, "MSFT", 2024, loss=750.0)

    result = runner.invoke(app, ["report", "--year", "2024"])

    assert result.exit_code == 0, result.output
    assert "Confirmed" in result.output
    # Total disallowed = 1000 + 500 + 750 = 2250
    assert "2,250" in result.output or "2250" in result.output
    assert DISCLAIMER in result.output


def test_report_year_filter(cli_setup):
    """--year 2024: 2023 violations not shown."""
    runner, engine, _ = cli_setup
    _seed_wash_sale(engine, "TSLA", 2024, loss=1000.0)
    _seed_wash_sale(engine, "AAPL", 2023, loss=800.0)

    result = runner.invoke(app, ["report", "--year", "2024"])

    assert result.exit_code == 0, result.output
    assert "TSLA" in result.output
    assert "AAPL" not in result.output


def test_report_csv_export(cli_setup, tmp_path, monkeypatch):
    """--csv: CSV file created with correct headers and one Confirmed row."""
    runner, engine, _ = cli_setup
    _seed_wash_sale(engine, "TSLA", 2024, loss=1000.0)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["report", "--year", "2024", "--csv"])

    assert result.exit_code == 0, result.output

    csv_files = list(tmp_path.glob("wash_sale_report_*.csv"))
    assert len(csv_files) == 1

    with open(csv_files[0]) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 1
    assert rows[0]["Ticker"] == "TSLA"
    assert rows[0]["Confidence"] == "Confirmed"
    assert "1000" in rows[0]["Disallowed"]


def test_report_empty(cli_setup):
    """No trades: 'No trades imported yet.' message, exit 0."""
    runner, engine, _ = cli_setup

    result = runner.invoke(app, ["report"])

    assert result.exit_code == 0, result.output
    assert "no trades" in result.output.lower()
    # No disclaimer when exiting early (no trades) — check report.py if needed
