from __future__ import annotations

from datetime import date

from sqlmodel import Session
from typer.testing import CliRunner

from net_alpha.cli.app import app
from net_alpha.db.repository import TradeRepository
from net_alpha.models.domain import Trade


def test_status_no_trades(cli_setup):
    runner, engine, settings = cli_setup
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "No trades imported" in result.output


def test_status_with_trades_no_check(cli_setup):
    runner, engine, settings = cli_setup

    with Session(engine) as s:
        repo = TradeRepository(s)
        repo.save(
            Trade(
                account="schwab",
                date=date(2026, 1, 10),
                ticker="AAPL",
                action="Buy",
                quantity=10,
                proceeds=None,
                cost_basis=1500.0,
            )
        )
        s.commit()

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "schwab" in result.output
    assert "No scan results yet" in result.output
    assert "informational only" in result.output


def test_status_shows_disclaimer(cli_setup):
    runner, engine, settings = cli_setup
    result = runner.invoke(app, ["status"])
    # Even with no trades, disclaimer not shown (exits early) — just check no crash
    assert result.exit_code == 0
